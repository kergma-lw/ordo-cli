"""Static possible-process topology. Never activate workflows or evaluate probes.

Address evidence and execution evidence are deliberately separate. Ordered sites
are occurrences, not a set of referenced fields; conditions remain symbolic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields, replace
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import authored_string_style
from ordo.model.workflow import GuardBlock, RunBlock, Step, StepBlock, Workflow
from ordo.runtime.fragment_runs import build_run_target_workflow
from ordo.runtime.loading import LoadError, load_workflow_document_file
from ordo.runtime.local_expression_engine.core import (
    BinaryNode, LiteralNode, ReferenceNode, StateReferenceNode, StepReferenceNode,
    ValueExpressionNode, ListNode, ObjectNode, PipelineNode, FilterApplicationNode, render_expression_text,
)
from ordo.runtime.profiles import apply_runtime_profile_switch, should_ignore_runtime_profile_switch
from ordo.runtime.local_expressions import LOCAL_EXPRESSION_PARSE_ERRORS, parse_value_local_expression
from ordo.runtime.state_paths import StatePathParseError, parse_state_path
from ordo.runtime.graph_structure import structural_relation


_UNKNOWN = object()
MAX_STATIC_CHOICES = 32


@dataclass(frozen=True)
class _Choices:
    """Finite authored possibilities, never sampled runtime values."""
    values: tuple


def _choices(values):
    unique = []
    for value in values:
        if value is _UNKNOWN:
            return _UNKNOWN
        for item in value.values if isinstance(value, _Choices) else (value,):
            if item not in unique:
                unique.append(item)
        if len(unique) > MAX_STATIC_CHOICES:
            return _UNKNOWN
    return unique[0] if len(unique) == 1 else _Choices(tuple(unique)) if unique else _UNKNOWN


def _lookup(value, key):
    if isinstance(key, _Choices):
        return _choices(_lookup(value, item) for item in key.values)
    if isinstance(value, _Choices):
        return _choices(_lookup(item, key) for item in value.values)
    return value.get(key, _UNKNOWN) if isinstance(value, dict) and isinstance(key, str) else _UNKNOWN


def _parse(text):
    try:
        parsed = parse_value_local_expression(text, allow_boolean_composition=True)
        return parsed.value.root, parsed.value.source
    except LOCAL_EXPRESSION_PARSE_ERRORS:
        return None, text


def _constant(node, workflow, seen=()):
    """A deliberately small literal/input/let evaluator, with no runtime fallback."""
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, ListNode):
        values = [_constant(item, workflow, seen) for item in node.items]
        return _UNKNOWN if any(value is _UNKNOWN for value in values) else values
    if isinstance(node, ObjectNode):
        values = {entry.key: _constant(entry.value, workflow, seen) for entry in node.entries}
        return _UNKNOWN if any(value is _UNKNOWN for value in values.values()) else values
    if isinstance(node, PipelineNode):
        value = _constant(node.source, workflow, seen)
        for stage in node.filters:
            if not isinstance(stage, FilterApplicationNode) or stage.name != "lookup" or len(stage.arguments) != 1:
                return _UNKNOWN
            value = _lookup(value, _constant(stage.arguments[0], workflow, seen))
        return value
    if isinstance(node, ReferenceNode):
        parts = node.parts
        if parts[0] in workflow.let_bindings and parts[0] not in seen:
            nested, _ = _parse(workflow.let_bindings[parts[0]])
            value = _constant(nested, workflow, (*seen, parts[0]))
            rest = parts[1:]
        elif parts[0] == "args":
            value, rest = workflow.inputs.get("__fragment_args__", {}), parts[1:]
        elif parts[0] == "inputs":
            value, rest = workflow.inputs, parts[1:]
        elif parts[0] == "item":
            value, rest = workflow.inputs.get("__iteration_item__", _UNKNOWN), parts[1:]
        else:
            return _UNKNOWN
        for part in rest:
            value = _lookup(value, part)
        return value
    return _UNKNOWN


def static_binding(value: object, workflow: Workflow) -> object:
    if isinstance(value, str):
        if authored_string_style(value) != "plain" and not (value.startswith("${") and value.endswith("}")):
            return str(value)
        node, _ = _parse(value)
        return _constant(node, workflow)
    if isinstance(value, list):
        result = [static_binding(item, workflow) for item in value]
        return _UNKNOWN if any(item is _UNKNOWN for item in result) else result
    if isinstance(value, dict):
        result = {key: static_binding(item, workflow) for key, item in value.items()}
        return _UNKNOWN if any(item is _UNKNOWN for item in result.values()) else result
    return value


class _Collector:
    def __init__(self, name, workflow, base_dir, profiles=None, profile_base_dir=None, catalog_complete=True,
                 families=None, namespace=""):
        self.name = name
        self.workflow = workflow
        self.base_dir = base_dir
        self.ambient_base = base_dir
        self.sites = []
        self.boundaries = []
        self.repeats = []
        self.profiles = profiles
        self.catalog_complete = catalog_complete and profiles is not None
        self.profile_base_dir = profile_base_dir or base_dir
        self.current_profile = workflow.launch_profile_name
        self.profile_domain = workflow.launch_profile_name
        self.phase = "body"
        self.namespace = namespace
        self.scope = name
        self.families = dict(families or {})
        self.family_values = dict(workflow.states)
        self.selection_origin = {"kind": "launch_profile", "scope": namespace or name}
        self.input_origins = {}
        self.arg_origins = {}
        self.item_origin = {"kind": "item", "scope": name}
        initial = (profiles or {}).get(workflow.launch_profile_name)
        if initial is not None:
            self._profile_origins(workflow, [initial], self.selection_origin)

    def _profile_origins(self, workflow, candidates, origin, conditional=False):
        protected = set(workflow.protected_input_keys) | set(workflow.explicit_input_keys)
        for key in set().union(*(p.inputs.keys() for p in candidates)) - protected if candidates else ():
            term = {"kind": "profile_input", "field": key, "selection": origin}
            if conditional or any(key not in p.inputs for p in candidates):
                term["fallback"] = self.input_origins.get(key, {"kind": "input", "scope": self.scope, "path": [key]})
            self.input_origins[key] = term

    def family(self, role, workflow, store):
        binding = workflow.state_bindings.get(role)
        if binding is None:
            return None
        raw = workflow.states.get(binding)
        declared = self.families.get(binding)
        if declared is not None and (raw == self.family_values.get(binding) or workflow.playbook_owned_pre_run):
            return dict(declared)
        # Without a playbook declaration, require the actual binding and path,
        # never just a role/name, to establish a family in an engine-supplied IR.
        if store is not None:
            return {"id": f"direct:{binding}:{store}", "name": binding, "instance_kind": "fixed"}
        return None

    def selector_origin(self, node, source, workflow, seen=()):
        if isinstance(node, LiteralNode):
            return {"kind": "literal", "value": node.value}
        if isinstance(node, ListNode):
            return {"kind": "list", "items": [self.selector_origin(item, source, workflow, seen) for item in node.items]}
        if isinstance(node, ObjectNode):
            return {"kind": "object", "entries": {entry.key: self.selector_origin(entry.value, source, workflow, seen)
                                                    for entry in node.entries}}
        if isinstance(node, ReferenceNode):
            root, *rest = node.parts
            if root in workflow.let_bindings and root not in seen:
                nested, text = _parse(workflow.let_bindings[root])
                origin = self.selector_origin(nested, text, workflow, (*seen, root))
            elif root == "inputs" and rest:
                key, *rest = rest
                origin = self.input_origins.get(key, {"kind": "input", "scope": self.scope, "path": [key]})
            elif root == "args" and rest:
                key, *rest = rest
                origin = self.arg_origins.get(key, {"kind": "argument", "scope": self.scope, "name": key})
            elif root == "item":
                origin = self.item_origin
            else:
                return {"kind": "reference", "scope": self.scope, "path": list(node.parts)}
            return {"kind": "projection", "source": origin, "fields": rest} if rest else origin
        if isinstance(node, StateReferenceNode):
            binding = workflow.state_bindings.get(node.state_role)
            raw = workflow.states.get(binding)
            store = None
            if isinstance(raw, str) and "${" not in raw:
                if os.path.isabs(raw):
                    store = os.path.normpath(raw)
                elif self.base_dir is not None:
                    store = os.path.abspath(os.path.join(self.base_dir, raw))
            key_value = _constant(node.key_expression, workflow)
            key_origin = ({"kind": "literal", "value": key_value} if isinstance(key_value, str)
                          else self.selector_origin(node.key_expression, source, workflow, seen))
            return {"kind": "state_value", "family": (self.family(node.state_role, workflow, store) or {}).get("id"),
                    "store": store, "key": key_origin, "fields": list(node.fields)}
        if isinstance(node, StepReferenceNode):
            return {"kind": "registered_result", "scope": self.scope, "register": node.register,
                    "fields": list(node.fields)}
        if isinstance(node, PipelineNode):
            return {"kind": "pipeline", "source": self.selector_origin(node.source, source, workflow, seen),
                    "stages": [{"name": stage.name,
                                "arguments": [self.selector_origin(arg, source, workflow, seen) for arg in stage.arguments]}
                               if isinstance(stage, FilterApplicationNode) else {"kind": "opaque", "scope": self.scope}
                               for stage in node.filters]}
        return {"kind": "expression", "scope": self.scope,
                "text": render_expression_text(node, source=source) if node is not None else source}

    def value_origin(self, value, workflow, path):
        if isinstance(value, str):
            node, source = _parse(value)
            if authored_string_style(value) == "plain" or value.startswith("${"):
                return self.selector_origin(node, source, workflow)
        return {"kind": "literal", "value": value} if isinstance(value, (str, int, float, bool)) or value is None else {
            "kind": "expression", "scope": self.scope, "path": path}

    def origin_frame(self):
        return (self.selection_origin, dict(self.input_origins), dict(self.arg_origins), self.item_origin,
                self.scope, dict(self.families), dict(self.family_values))

    def restore_origins(self, frame):
        (self.selection_origin, self.input_origins, self.arg_origins, self.item_origin,
         self.scope, self.families, self.family_values) = frame

    def boundary(self, path, reason, **details):
        self.boundaries.append({"path": path, "reason": reason, "phase": self.phase,
                                "impact": "structure", **details})

    def profile_directory(self, profile, workflow):
        raw = profile.working_directory
        if raw is None:
            return self.ambient_base
        value = static_binding(raw, workflow) if raw.startswith("${") else raw
        if not isinstance(value, str):
            return None
        if os.path.isabs(value):
            return os.path.normpath(value)
        return os.path.abspath(os.path.join(self.profile_base_dir, value)) if self.profile_base_dir else None

    def switch_profile(self, workflow, target, path, *, conditional=False, bound=False, origin=None):
        # A playbook-owned pre_run cannot override an explicit CLI profile. Its
        # state read remains evidence, but uncertainty in that value is not an
        # unknown main-workflow access footprint.
        if not bound and workflow.playbook_owned_pre_run and workflow.launch_profile_source == "explicit_cli":
            if isinstance(target, str) and should_ignore_runtime_profile_switch(workflow, target_profile_name=target):
                return workflow
            if not isinstance(target, str):
                # Unknown bootstrap selection can either select the explicit
                # launch profile or be ignored. A bound enclosing workflow may
                # have a different current profile; do not conflate the two.
                selected = (self.profiles or {}).get(workflow.launch_profile_name)
                if selected is not None:
                    applied = apply_runtime_profile_switch(workflow, selected).workflow
                    if (self.current_profile == selected.name and applied.inputs == workflow.inputs
                            and self.profile_directory(selected, applied) == self.base_dir):
                        return workflow
                    target = workflow.launch_profile_name
                    conditional = True
        profile = (self.profiles or {}).get(target) if isinstance(target, str) else None
        selection = origin or {"kind": "profile_selection", "scope": self.scope, "path": path,
                               "name": target if isinstance(target, str) else None}
        if conditional:
            selection = {"kind": "conditional_selection", "scope": self.scope, "path": path,
                         "choices": [self.selection_origin, selection]}
        if profile is not None and not conditional:
            self._profile_origins(workflow, [profile], selection)
            self.selection_origin = selection
            result = apply_runtime_profile_switch(workflow, profile).workflow
            self.base_dir = self.profile_directory(profile, result)
            self.current_profile = profile.name
            self.profile_domain = profile.name
            if self.base_dir is None:
                self.boundary(path, "profile_directory_unresolved", impact="context", target=profile.name)
            return result
        candidates = list((self.profiles or {}).values())
        if isinstance(target, str) and profile is None:
            candidates = []
        elif isinstance(target, _Choices) and all(isinstance(name, str) and name in (self.profiles or {}) for name in target.values):
            candidates = [self.profiles[name] for name in target.values]
        elif profile is not None:
            candidates = [profile]
        self._profile_origins(workflow, candidates, selection, conditional)
        self.selection_origin = selection
        inputs = dict(workflow.inputs)
        protected = set(workflow.protected_input_keys) | set(workflow.explicit_input_keys)
        if self.catalog_complete and candidates:
            variants = [apply_runtime_profile_switch(workflow, item).workflow for item in candidates]
            if conditional:
                variants.append(workflow)
            for key in set().union(*(item.inputs.keys() for item in variants)) - protected:
                value = _choices(item.inputs.get(key, _UNKNOWN) for item in variants)
                if value is _UNKNOWN:
                    inputs.pop(key, None)
                else:
                    inputs[key] = value
            directories = [self.profile_directory(profile, item) for profile, item in zip(candidates, variants)]
            if conditional:
                directories.append(self.base_dir)
            directory = _choices(directories)
            self.base_dir = directory if isinstance(directory, str) else None
        else:
            inputs = {key: value for key, value in inputs.items() if key in protected}
            self.base_dir = None
        names = [item.name for item in candidates]
        if conditional:
            names.append(self.profile_domain)
        self.profile_domain = _choices(names) if self.catalog_complete and candidates else _UNKNOWN
        self.current_profile = self.profile_domain if isinstance(self.profile_domain, str) else None
        self.boundary(path, "profile_context_unresolved", impact="context",
                      target=target if isinstance(target, str) else None,
                      candidates=[item.name for item in candidates])
        return replace(workflow, inputs=inputs)

    def address(self, role, key, field_path, workflow, source):
        binding = workflow.state_bindings.get(role)
        raw = workflow.states.get(binding)
        store = None
        if isinstance(raw, str) and "${" not in raw:
            if os.path.isabs(raw):
                store = os.path.normpath(raw)
            elif self.base_dir is not None:
                store = os.path.abspath(os.path.join(self.base_dir, raw))
        value = _constant(key, workflow)
        # Runtime keys must be nonempty strings. Unknown is not a shared symbol.
        known_key = isinstance(value, str) and bool(value)
        address = {
            "role": role, "binding": binding, "store": store,
            "store_identity": "proven" if store is not None else "unresolved",
            "key": value if known_key else None,
            "key_expression": render_expression_text(key, source=source),
            "key_identity": "proven" if known_key else "unresolved",
            "symbol_scope": self.name,
            "fields": list(field_path),
        }
        if isinstance(value, _Choices) and all(isinstance(item, str) and item for item in value.values):
            address["key_candidates"] = list(value.values)
        origin = self.selector_origin(key, source, workflow)
        def profile_derived(term):
            return isinstance(term, dict) and (term.get("kind") == "profile_input"
                or any(profile_derived(item) for item in term.values())) or (
                    isinstance(term, list) and any(profile_derived(item) for item in term))
        fixed = known_key and not profile_derived(origin)
        address["selector"] = {"kind": "fixed" if fixed else "parameter",
                               "origin": {"kind": "literal", "value": value} if fixed else origin}
        if fixed:
            address["selector"].update(value=value, closed_domain=[value])
        elif "key_candidates" in address and not profile_derived(origin):
            address["selector"]["closed_domain"] = list(address["key_candidates"])
        family = self.family(role, workflow, store)
        if family is not None:
            address["family"] = family
        return address

    def emit(self, kind, role, key, field_path, workflow, source, path, conditions):
        site = {
            "id": f"{self.name}:{len(self.sites)}", "workflow": self.name,
            "order": len(self.sites), "path": path, "source": workflow.source_path,
            "kind": kind, "expression": source, "conditions": list(conditions),
            "phase": self.phase, "profile": self.current_profile, "working_directory": self.base_dir,
            "address": self.address(role, key, field_path, workflow, source),
        }
        if isinstance(self.profile_domain, _Choices):
            site["profile_candidates"] = list(self.profile_domain.values)
        self.sites.append(site)

    def expression(self, value, workflow, path, conditions, seen=(), *, native=False):
        if isinstance(value, dict):
            if native and len(value) == 1:
                operator, items = next(iter(value.items()))
                if operator in {"all", "any"} and isinstance(items, list):
                    for index, item in enumerate(items):
                        prior = [] if index == 0 else [{"kind": "short_circuit", "operator": operator,
                                                      "expressions": items[:index]}]
                        self.expression(item, workflow, f"{path}.{operator}.{index}",
                                        [*conditions, *prior], seen, native=True)
                    return
            for key, item in value.items():
                self.expression(item, workflow, f"{path}.{key}", conditions, seen, native=native)
            return
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                self.expression(item, workflow, f"{path}.{index}", conditions, seen, native=native)
            return
        if not isinstance(value, str):
            return
        if not native and authored_string_style(value) != "plain" and not (value.startswith("${") and value.endswith("}")):
            return
        node, source = _parse(value)
        if node is None:
            if "state." in value:
                self.boundary(path, "unparsed_expression", expression=value)
            return
        self.visit(node, source, workflow, path, conditions, seen)

    def visit(self, node, source, workflow, path, conditions, seen):
        if isinstance(node, StateReferenceNode):
            self.visit(node.key_expression, source, workflow, path + ".key", conditions, seen)
            self.emit("read", node.state_role, node.key_expression, node.fields,
                      workflow, source, path, conditions)
            return
        if isinstance(node, StepReferenceNode):
            return  # Reading a registered value never rereads its original storage.
        if isinstance(node, ReferenceNode):
            name = node.parts[0]
            if name in workflow.let_bindings:
                if name in seen:
                    self.boundary(path, "recursive_let", name=name)
                else:
                    self.expression(workflow.let_bindings[name], workflow,
                                    path + ".let." + name, conditions, (*seen, name), native=True)
            return
        if isinstance(node, BinaryNode):
            self.visit(node.left, source, workflow, path, conditions, seen)
            right_conditions = conditions
            if node.operator in ("and", "or"):
                right_conditions = [*conditions, {"kind": "short_circuit", "operator": node.operator,
                    "expression": render_expression_text(node.left, source=source)}]
            self.visit(node.right, source, workflow, path, right_conditions, seen)
            return
        if isinstance(node, ValueExpressionNode):
            for field in fields(node):
                value = getattr(node, field.name)
                for child in value if isinstance(value, tuple) else (value,):
                    if isinstance(child, ValueExpressionNode):
                        self.visit(child, source, workflow, path, conditions, seen)

    def mutation(self, expression, kind, workflow, path, conditions):
        try:
            parsed = parse_state_path(expression)
        except StatePathParseError:
            self.boundary(path, "unparsed_address", expression=expression)
            return
        key, source = _parse(parsed.key_expression)
        if key is None:
            self.boundary(path, "unparsed_key", expression=parsed.key_expression)
            return
        self.visit(key, source, workflow, path + ".key", conditions, ())
        self.emit(kind, parsed.state_role, key, parsed.fields, workflow, source, path, conditions)

    def walk(self, workflow, prefix="blocks", conditions=(), stack=()):
        saved = self.base_dir, self.current_profile, self.phase, self.ambient_base, self.profile_domain
        saved_origins = self.origin_frame()
        self.ambient_base = self.base_dir
        if workflow.playbook_owned_pre_run:
            self.phase = "bootstrap"
        if workflow.profile is not None and workflow.profile != self.current_profile:
            workflow = self.switch_profile(workflow, workflow.profile, prefix, bound=True)
        elif workflow.profile is not None:
            self.current_profile = workflow.profile
            self.profile_domain = workflow.profile
        active = list(conditions)
        for index, block in enumerate(workflow.blocks):
            path = f"{prefix}.{index}"
            if isinstance(block, GuardBlock):
                for number, guard in enumerate(block.guards):
                    value = guard.expr if guard.expr is not None else guard.operation.with_
                    self.expression(value, workflow, f"{path}.guards.{number}", active, native=guard.expr is not None)
                    active.append({"kind": "guard", "expression": guard.to_contract()})
            elif isinstance(block, StepBlock):
                active, workflow = self.steps(block.steps, workflow, path + ".steps", active, stack)
            elif isinstance(block, RunBlock):
                step = Step(name=block.run, run=block.run, run_with=block.with_,
                            if_=block.if_, resolved_run_path=block.resolved_path)
                active, workflow = self.steps((step,), workflow, path + ".run", active, stack)
        result = workflow, self.current_profile, self.base_dir, self.profile_domain, self.selection_origin
        self.base_dir, self.current_profile, self.phase, self.ambient_base, self.profile_domain = saved
        self.restore_origins(saved_origins)
        return result

    def steps(self, steps, workflow, prefix, inherited, stack):
        active = list(inherited)
        for index, step in enumerate(steps):
            path = f"{prefix}.{index}"
            local = list(active)
            self.expression(step.if_, workflow, path + ".if", local, native=True)
            if step.if_ is not None:
                local.append({"kind": "if", "expression": step.if_})
            self.expression(step.gate, workflow, path + ".gate", local, native=True)
            if step.gate is not None:
                local.append({"kind": "gate", "expression": step.gate})
                active.append({"kind": "conditional_gate", "if": step.if_, "expression": step.gate})
            self.expression(step.for_each, workflow, path + ".for_each", local)
            if step.for_each is not None:
                repeat = {"path": path, "expression": step.for_each, "representation": "symbolic_body"}
                self.repeats.append(repeat)
                local.append({"kind": "iteration", **repeat})
            for surface in ("value", "result", "publish", "profile_switch"):
                self.expression(getattr(step, surface), workflow, path + "." + surface, local)
            legacy_switch = step.operation is not None and step.operation.uses == "runtime.profile.use"
            profile_value = step.profile_switch
            if legacy_switch:
                self.expression(step.operation.with_, workflow, path + ".with", local)
                profile_value = step.operation.with_.get("profile")
            if profile_value is not None:
                workflow = self.switch_profile(workflow, static_binding(profile_value, workflow), path,
                                               conditional=step.if_ is not None,
                                               origin=self.value_origin(profile_value, workflow, path))
            if step.operation and not legacy_switch:
                self.expression(step.operation.with_, workflow, path + ".with", local)
            if step.state_set is not None:
                # The mutation payload is evaluated before storage is replaced.
                for target, value in step.state_set.items():
                    self.expression(value, workflow, path + ".state_set.value", local)
                    self.mutation(target, "set", workflow, path + ".state_set", local)
            if step.state_delete is not None:
                self.mutation(step.state_delete, "delete", workflow, path + ".state_delete", local)
            if step.steps is not None:
                caller_base, caller_profile, caller_ambient, caller_domain = self.base_dir, self.current_profile, self.ambient_base, self.profile_domain
                caller_origins = self.origin_frame()
                self.ambient_base = caller_base
                repeated = replace(self.iteration_workflow(step, workflow, path), let_bindings={}, profile=None)
                self.item_origin = {"kind": "iteration_item", "scope": self.scope, "path": path}
                self.scope = f"{self.scope}/{path}.body"
                self.steps(step.steps, repeated, path + ".body", local, stack)
                final_domain = self.profile_domain
                final_origin = self.selection_origin
                self.base_dir, self.current_profile, self.ambient_base, self.profile_domain = caller_base, caller_profile, caller_ambient, caller_domain
                self.restore_origins(caller_origins)
                if workflow.profile is None and (final_domain != caller_domain or final_origin != self.selection_origin):
                    workflow = self.switch_profile(workflow, final_domain, path, conditional=True, origin=final_origin)
                active.append({"kind": "invocation_completed", "path": path, "if": step.if_})
            if step.run is not None:
                self.expression(step.run_with, workflow, path + ".with", local)
                result = self.call(step, self.iteration_workflow(step, workflow, path), path, local, stack)
                if (result is None and workflow.profile is None
                        and not (step.run_origin == "playbook_pre_run" and workflow.launch_profile_source == "explicit_cli")):
                    workflow = self.switch_profile(workflow, _UNKNOWN, path, conditional=True)
                elif result is not None and workflow.profile is None and result[0].profile is None:
                    if result[3] != self.profile_domain or result[4] != self.selection_origin:
                        workflow = self.switch_profile(workflow, result[3], path,
                                                        conditional=step.if_ is not None or step.for_each is not None,
                                                        origin=result[4])
                active.append({"kind": "invocation_completed", "path": path, "if": step.if_})
        return active, workflow

    def iteration_workflow(self, step, workflow, path):
        if step.for_each is None:
            return workflow
        values = static_binding(step.for_each, workflow)
        item = _choices(values) if isinstance(values, list) and len(values) <= MAX_STATIC_CHOICES else _UNKNOWN
        if isinstance(values, list) and len(values) > MAX_STATIC_CHOICES:
            self.boundary(path, "static_item_domain_limit", impact="context", limit=MAX_STATIC_CHOICES)
        inputs = dict(workflow.inputs)
        inputs.pop("__iteration_item__", None)
        if item is not _UNKNOWN:
            inputs["__iteration_item__"] = item
        return replace(workflow, inputs=inputs)

    def call(self, step, workflow, path, conditions, stack):
        target = step.resolved_run_path
        if len(stack) >= 32:
            self.boundary(path, "composition_depth_limit", target=step.run, limit=32)
            return
        if target is None or target in stack:
            self.boundary(path, "recursion" if target in stack else "unresolved_call", target=step.run)
            return
        # Unknown arguments remain symbolic inputs, never fake concrete values.
        bindings = {key: static_binding(value, workflow) for key, value in step.run_with.items()}
        known = {key: value for key, value in bindings.items() if value is not _UNKNOWN}
        launch_dir = Path(workflow.launch_dir or self.base_dir or ".")
        # Load source structure, not runtime argument materialization: an unknown
        # typed argument is not a reason to erase an otherwise known body.
        try:
            payload = load_workflow_document_file(target, launch_dir=launch_dir)
        except LoadError as exc:
            self.boundary(path, "unresolved_call", target=step.run,
                          diagnostics=[d.to_contract() for d in exc.diagnostics])
            return
        arguments = payload.get("args", {})
        if isinstance(arguments, dict):
            for key, spec in arguments.items():
                if key not in bindings and isinstance(spec, dict) and "default" in spec:
                    known[key] = spec["default"]
        payload = {key: value for key, value in payload.items() if key not in {"args", "description"}}
        nested = build_run_target_workflow(payload, caller_workflow=workflow, step=step,
            run_path=Path(target), launch_dir=launch_dir, node_path=(path,), bindings=known)
        if isinstance(nested, Diagnostic):
            self.boundary(path, "unresolved_call", target=step.run, diagnostic=nested.to_contract())
            return
        inputs = dict(nested.inputs)
        for key, value in bindings.items():
            if value is _UNKNOWN:
                inputs.pop(key, None)
        if step.for_each is not None and "__iteration_item__" in workflow.inputs:
            inputs["__fragment_args__"] = {**inputs.get("__fragment_args__", {}), "item": workflow.inputs["__iteration_item__"]}
        saved_origins = self.origin_frame()
        supplied_origins = {key: self.value_origin(value, workflow, path + ".with." + key)
                            for key, value in step.run_with.items()}
        self.input_origins = {key: self.input_origins.get(key, {"kind": "input", "scope": self.scope, "path": [key]})
                              for key in set(workflow.inputs) | set(workflow.declared_inputs)
                              if key in workflow.inputs or key not in nested.inputs}
        self.input_origins.update(supplied_origins)
        self.arg_origins = dict(supplied_origins)
        if step.for_each is not None:
            self.item_origin = {"kind": "iteration_item", "scope": self.scope, "path": path}
            self.arg_origins["item"] = self.item_origin
        self.scope = f"{self.scope}/{path}.call"
        for name, location in nested.states.items():
            if location != workflow.states.get(name) and step.run_origin != "playbook_pre_run":
                owner = str(target) if name in payload.get("states", {}) else self.scope
                self.families[name] = {"id": f"source:{owner}#states.{name}", "name": name,
                                       "instance_kind": "fixed" if os.path.isabs(location) else "profile_instance"}
        self.family_values = dict(nested.states)
        try:
            return self.walk(replace(nested, inputs=inputs), path + ".call", conditions, (*stack, target))
        finally:
            self.restore_origins(saved_origins)


def _relation(left, right):
    a, b = left["address"], right["address"]
    if a["store"] is not None and b["store"] is not None and a["store"] != b["store"]:
        return None
    if a["key"] is not None and b["key"] is not None and a["key"] != b["key"]:
        return None
    a_keys = [a["key"]] if a["key"] is not None else a.get("key_candidates")
    b_keys = [b["key"]] if b["key"] is not None else b.get("key_candidates")
    if a_keys is not None and b_keys is not None and not set(a_keys).intersection(b_keys):
        return None
    x, y = a["fields"], b["fields"]
    if x[:len(y)] != y and y[:len(x)] != x:
        return None
    proven = all(item["store_identity"] == item["key_identity"] == "proven" for item in (a, b))
    relation = "exact" if x == y else "ancestor" if y[:len(x)] == x else "descendant"
    return {"address_identity": "proven" if proven else "possible", "field_relation": relation,
            "execution": "possible", "empty_parent_prune": left["kind"] == "delete" and relation == "descendant"}


def _components(names, links, *, directed):
    adjacent = {name: set() for name in names}
    for link in links:
        adjacent[link["from_workflow"]].add(link["to_workflow"])
        if not directed:
            adjacent[link["to_workflow"]].add(link["from_workflow"])
    def reachable(start):
        found, todo = set(), [start]
        while todo:
            item = todo.pop()
            if item not in found:
                found.add(item)
                todo.extend(adjacent[item] - found)
        return found
    reach = {name: reachable(name) for name in names}
    remaining, result = set(names), []
    for name in names:
        if name not in remaining:
            continue
        component = sorted(other for other in reach[name] if not directed or name in reach[other])
        remaining.difference_update(component)
        if not directed or len(component) > 1:
            result.append(component)
    return result


def build_static_graph(
    workflows: list[tuple[str, Workflow, str | None]], *,
    playbook_path: str = "", boundaries: list[dict[str, object]] | tuple = (),
    profiles=None, profile_base_dir=None, catalog_complete=True,
    state_families=None, workflow_categories=None,
) -> dict[str, object]:
    """Build schema v1 from (public name, Workflow, static working directory)."""
    nodes, accesses, orders = [], [], []
    for name, workflow, base_dir in workflows:
        collector = _Collector(name, workflow, base_dir, profiles, profile_base_dir, catalog_complete,
                               (state_families or {}).get(name), playbook_path)
        if (workflow.profile is None and workflow.launch_profile_source != "explicit_cli"
                and any(b.get("workflow") == name and b.get("phase") == "bootstrap" for b in boundaries)):
            collector.phase = "bootstrap"
            workflow = collector.switch_profile(workflow, _UNKNOWN, "pre_run", conditional=True)
            collector.phase = "body"
        collector.walk(workflow, stack=(workflow.source_path,) if workflow.source_path else ())
        nodes.append({"workflow": name, "accesses": [site["id"] for site in collector.sites],
                      "boundaries": collector.boundaries, "repeats": collector.repeats})
        if (workflow_categories or {}).get(name) is not None:
            nodes[-1]["category"] = workflow_categories[name]
        accesses.extend(collector.sites)
        orders.extend({"from": a["id"], "to": b["id"], "kind": "authored_order"}
                      for a, b in zip(collector.sites, collector.sites[1:]))
    links, structural_links = [], []
    for writer in accesses:
        if writer["kind"] not in ("set", "delete"):
            continue
        for reader in accesses:
            if reader["kind"] != "read" or writer["workflow"] == reader["workflow"]:
                continue
            evidence = _relation(writer, reader)
            if evidence is not None:
                links.append({"from": writer["id"], "to": reader["id"],
                    "from_workflow": writer["workflow"], "to_workflow": reader["workflow"],
                    "kind": "handoff" if writer["kind"] == "set" else "invalidation", **evidence})
            structural = structural_relation(writer, reader, evidence)
            if structural is not None:
                structural_links.append({"from": writer["id"], "to": reader["id"],
                    "from_workflow": writer["workflow"], "to_workflow": reader["workflow"],
                    "kind": "handoff" if writer["kind"] == "set" else "invalidation", **structural})
    names = [node["workflow"] for node in nodes]
    body_ids = {site["id"] for site in accesses if site["phase"] == "body"}
    business_links = [link for link in links if link["from"] in body_ids and link["to"] in body_ids]
    structural_body = [link for link in structural_links if link["from"] in body_ids and link["to"] in body_ids]
    payload = {"schema": "ordo.static-process-graph", "schema_version": 1, "mode": "graph",
        "playbook": playbook_path, "workflows": nodes, "accesses": accesses,
        "order_edges": orders, "links": links, "components": _components(names, links, directed=False),
        "possible_loop_components": _components(names, links, directed=True),
        "business_components": _components(names, business_links, directed=False),
        "structural_links": structural_links,
        "structural_components": _components(names, [*business_links, *structural_body], directed=False),
        "structural_loop_components": _components(names, [*business_links, *structural_body], directed=True),
        "boundaries": list(boundaries), "activity": {"status": "not_requested"},
        "semantics": "Static possible processes; address identity is not execution or reachability proof. "
                     "Conditions and repeats are symbolic; components may contain incompatible paths."}
    from .graph_summary import summarize_static_graph

    payload["summary"] = summarize_static_graph(payload)
    return payload


def render_static_graph(payload: dict[str, object]) -> str:
    from .graph_summary import render_graph_summary

    return render_graph_summary(payload)
