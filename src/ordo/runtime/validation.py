"""Strict validation for workflow and profile declarations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONValue, authored_string_style
from ordo.model.profile_contract import PROFILE_CONTRACT
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import StepBlock, Workflow
from ordo.routines import (
    ROUTINE_ENV_REFERENCE_PATTERN,
    ROUTINE_REFERENCE_PREFIX,
    RoutineRegistry,
    RoutineRegistryError,
    load_workflow_routine_registry,
    parse_routine_reference,
    validate_workflow_routine_invocations,
    workflow_uses_routine,
)
from ordo.model.workflow_contract import WORKFLOW_CONTRACT

from .local_expression_contexts import LocalExpressionContext
from .local_expressions import (
    LOCAL_EXPRESSION_PARSE_ERRORS,
    build_local_expression_parse_diagnostic,
    build_local_expression_validation_diagnostic,
    parse_condition_local_expression,
    parse_embedded_value_local_expression,
    parse_embedded_local_expression,
    parse_local_expression,
    parse_value_local_expression,
    validate_parsed_local_expression,
)
from .fragment_runs import build_run_target_workflow, load_run_target_payload
from .loading import LoadError, load_yaml_document
from .state_paths import StatePathParseError, parse_state_path
from .local_expression_engine.core import (
    AdapterBindingNode,
    AdapterInvocationNode,
    _FieldPathSyntaxError,
    _parse_field_path,
    BinaryNode,
    CallArgumentNode,
    CallNode,
    BuiltinCallNode,
    FilterApplicationNode,
    ListNode,
    LiteralNode,
    ObjectEntryNode,
    ObjectNode,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode as ValueStateReferenceNode,
    StepReferenceNode,
    UnaryNode,
    VALUE_EXPRESSION_FILTERS,
    ValueExpressionNode,
    collect_step_references,
)
from .static_expression_diagnostics import collect_static_expression_diagnostics

LET_RESERVED_NAMES = frozenset({"inputs", "args", "state", "step"})

USES_PATTERN = re.compile(r"^[a-z0-9]+([._-][a-z0-9]+)*$")
REGISTER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
LAUNCHER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def _field_names(items: list[JSONObject]) -> frozenset[str]:
    return frozenset(item["name"] for item in items if isinstance(item.get("name"), str))


WORKFLOW_ALLOWED_FIELDS = _field_names(WORKFLOW_CONTRACT["top_level_fields"])
BLOCK_ALLOWED_FIELDS = frozenset({"guards", "steps", "include", "with"})
CALL_ALLOWED_FIELDS = frozenset({"uses", "with"})
STEP_ALLOWED_FIELDS = frozenset().union(
    *(
        frozenset(form["required_fields"]) | frozenset(form["optional_fields"])
        for form in WORKFLOW_CONTRACT["step_forms"]
        if isinstance(form, dict)
    )
) | frozenset({"__run_path__"})
PROFILE_ALLOWED_FIELDS = _field_names(PROFILE_CONTRACT["top_level_fields"])
OVERRIDE_ALLOWED_FIELDS = _field_names(PROFILE_CONTRACT["override_fields"])
LAUNCHER_ALLOWED_FIELDS = _field_names(PROFILE_CONTRACT["launcher_fields"])


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Machine-usable validation result."""

    document_kind: str
    status: RuntimeStatus
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is RuntimeStatus.OK


def validate_workflow_text(text: str, *, source: str = "<memory>") -> ValidationReport:
    """Validate workflow YAML text against the stable v0 contract."""

    try:
        payload = load_yaml_document(text, source=source)
    except LoadError as exc:
        return ValidationReport(document_kind="workflow", status=RuntimeStatus.VALIDATION_ERROR, diagnostics=exc.diagnostics)

    return validate_workflow_document(payload, source=source)


def validate_profile_text(text: str, *, source: str = "<memory>") -> ValidationReport:
    """Validate profile YAML text against the current v0 profile contract."""

    try:
        payload = load_yaml_document(text, source=source)
    except LoadError as exc:
        return ValidationReport(document_kind="profile", status=RuntimeStatus.VALIDATION_ERROR, diagnostics=exc.diagnostics)

    return validate_profile_document(payload, source=source)


def validate_workflow_document(payload: JSONValue, *, source: str = "<memory>") -> ValidationReport:
    """Validate canonical JSON-shaped workflow data."""

    diagnostics: list[Diagnostic] = []

    if not isinstance(payload, dict):
        diagnostics.append(_diagnostic("validation.workflow.root_type", "Workflow root must be an object", (), source, actual_type=type(payload).__name__))
        return ValidationReport(document_kind="workflow", status=RuntimeStatus.VALIDATION_ERROR, diagnostics=tuple(diagnostics))

    diagnostics.extend(_validate_unknown_fields(payload, WORKFLOW_ALLOWED_FIELDS, path=(), source=source))
    diagnostics.extend(_require_exact_int(payload, "version", 0, source=source))
    diagnostics.extend(_require_non_empty_string(payload, "workflow", source=source))
    diagnostics.extend(_require_object_field(payload, "inputs", source=source, required=False))
    diagnostics.extend(_validate_workflow_input_declarations(payload.get("inputs"), source=source))
    diagnostics.extend(_require_object_field(payload, "let", source=source, required=False))
    diagnostics.extend(_validate_workflow_let_declarations(payload.get("let"), source=source))
    diagnostics.extend(_require_object_field(payload, "state_needs", source=source, required=False))
    diagnostics.extend(_validate_workflow_blocks(payload, source=source, let_bindings=payload.get("let") if isinstance(payload.get("let"), dict) else {}))
    diagnostics.extend(_validate_declared_workflow_input_references(payload, source=source))
    diagnostics.extend(_validate_state_role_write_order(payload, source=source))

    return _report("workflow", diagnostics)


def _validate_workflow_blocks(payload: JSONObject, *, source: str, let_bindings: JSONObject) -> list[Diagnostic]:
    return _validate_block_list(payload.get("blocks"), source=source, let_bindings=let_bindings)


def _validate_workflow_input_declarations(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    if not isinstance(value, dict):
        return []
    diagnostics: list[Diagnostic] = []
    for input_name, declaration in value.items():
        if not isinstance(input_name, str):
            continue
        if not isinstance(declaration, dict):
            continue
        hint = declaration.get("hint")
        if hint is not None and not isinstance(hint, str):
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.inputs.hint.type",
                    "Workflow input field 'hint' must be a string when present",
                    ("inputs", input_name, "hint"),
                    source,
                    input=input_name,
                    actual_type=type(hint).__name__,
                )
            )
    return diagnostics


def _validate_workflow_let_declarations(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    if not isinstance(value, dict):
        return []
    diagnostics: list[Diagnostic] = []
    for binding_name, expression in value.items():
        path = ("let", str(binding_name))
        if not isinstance(binding_name, str) or not binding_name:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.let.name",
                    "Workflow let binding names must be non-empty strings",
                    path,
                    source,
                )
            )
            continue
        if binding_name in LET_RESERVED_NAMES:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.let.reserved_name",
                    f"Workflow let binding name '{binding_name}' is reserved",
                    path,
                    source,
                    name=binding_name,
                )
            )
        if not isinstance(expression, str):
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.let.value_type",
                    "Workflow let binding values must be strings",
                    path,
                    source,
                    name=binding_name,
                    actual_type=type(expression).__name__,
                )
            )
            continue
        try:
            parsed = parse_local_expression(expression, context=LocalExpressionContext.STEP_CONDITION, allow_boolean_composition=True)
        except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
            diagnostics.append(
                Diagnostic(
                    code="validation.workflow.let.syntax",
                    level="error",
                    message=f"Workflow let binding '{binding_name}' is not a valid local expression",
                    path=path,
                    details={
                        "source": source,
                        "name": binding_name,
                        "expression": expression,
                        "position": exc.position,
                        "end": exc.end if exc.end is not None else exc.position,
                        "parse_message": exc.message,
                    },
                )
            )
            continue
        chained_bindings = _collect_direct_let_references(parsed.root, value)
        if chained_bindings:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.let.binding_chain",
                    f"Workflow let binding '{binding_name}' must not reference another let binding",
                    path,
                    source,
                    name=binding_name,
                    chained_bindings=sorted(chained_bindings),
                )
            )
    return diagnostics


def _collect_direct_let_references(node: ValueExpressionNode, let_bindings: JSONValue) -> set[str]:
    if not isinstance(let_bindings, dict):
        return set()
    found: set[str] = set()

    def visit(current: ValueExpressionNode) -> None:
        if isinstance(current, ReferenceNode):
            if current.parts and current.parts[0] in let_bindings:
                found.add(current.parts[0])
            return
        if isinstance(current, (LiteralNode, ValueStateReferenceNode, StepReferenceNode)):
            return
        if isinstance(current, ListNode):
            for item in current.items:
                visit(item)
            return
        if isinstance(current, ObjectEntryNode):
            visit(current.value)
            return
        if isinstance(current, ObjectNode):
            for entry in current.entries:
                visit(entry)
            return
        if isinstance(current, AdapterBindingNode):
            visit(current.value)
            return
        if isinstance(current, AdapterInvocationNode):
            for binding in current.bindings:
                visit(binding)
            return
        if isinstance(current, PipelineNode):
            visit(current.source)
            for item in current.filters:
                visit(item)
            return
        if isinstance(current, FilterApplicationNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, BuiltinCallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, UnaryNode):
            visit(current.operand)
            return
        if isinstance(current, BinaryNode):
            visit(current.left)
            visit(current.right)

    visit(node)
    return found


def _validate_declared_workflow_input_references(payload: JSONObject, *, source: str) -> list[Diagnostic]:
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return []

    declared_inputs = payload.get("inputs")
    declared_keys = set(declared_inputs) if isinstance(declared_inputs, dict) else set()
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[tuple[str, ...], str]] = set()

    for block_index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        guards = block.get("guards")
        if isinstance(guards, list):
            for guard_index, guard in enumerate(guards):
                item_path = ("blocks", str(block_index), "guards", str(guard_index))
                for reference in _collect_input_references_from_guard_item(guard):
                    _append_undeclared_input_reference_diagnostic(
                        diagnostics,
                        seen=seen,
                        reference=reference,
                        declared_keys=declared_keys,
                        path=item_path,
                        source=source,
                    )
        steps = block.get("steps")
        if isinstance(steps, list):
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                for reference, path in _iter_input_references_from_step_item(step, block_index=block_index, step_index=step_index):
                    _append_undeclared_input_reference_diagnostic(
                        diagnostics,
                        seen=seen,
                        reference=reference,
                        declared_keys=declared_keys,
                        path=path,
                        source=source,
                    )
    return diagnostics


def _append_undeclared_input_reference_diagnostic(
    diagnostics: list[Diagnostic],
    *,
    seen: set[tuple[tuple[str, ...], str]],
    reference: tuple[str, ...],
    declared_keys: set[str],
    path: tuple[str, ...],
    source: str,
) -> None:
    if len(reference) < 2 or reference[0] != "inputs":
        return
    input_name = reference[1]
    if input_name in declared_keys:
        return
    key = (path, input_name)
    if key in seen:
        return
    seen.add(key)
    diagnostics.append(
        _diagnostic(
            "validation.workflow.inputs.undeclared_reference",
            f"Workflow input reference '{'.'.join(reference)}' is not declared in the root workflow inputs contract",
            path,
            source,
            input=input_name,
            reference=".".join(reference),
        )
    )


def _collect_input_references_from_guard_item(item: JSONValue) -> set[tuple[str, ...]]:
    if isinstance(item, str):
        try:
            parsed = parse_local_expression(item, context=LocalExpressionContext.GUARD)
        except LOCAL_EXPRESSION_PARSE_ERRORS:
            return set()
        return _collect_value_input_references(parsed.value.root)
    if isinstance(item, dict):
        return _collect_input_references_from_runtime_value_surface(item.get("with"))
    return set()


def _iter_input_references_from_step_item(step: JSONObject, *, block_index: int, step_index: int) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    references: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    base_path = ("blocks", str(block_index), "steps", str(step_index))
    condition = step.get("if")
    if isinstance(condition, str):
        try:
            parsed = parse_condition_local_expression(condition, context=LocalExpressionContext.STEP_CONDITION)
        except LOCAL_EXPRESSION_PARSE_ERRORS:
            parsed = None
        if parsed is not None and parsed.value is not None:
            for reference in _collect_value_input_references(parsed.value.root):
                references.append((reference, base_path + ("if",)))
    if "for_each" in step:
        references.extend(_pair_input_references_with_paths(_collect_input_references_from_runtime_value_surface(step.get("for_each")), path=base_path + ("for_each",)))
    if "uses" in step or "run" in step:
        references.extend(_pair_input_references_with_paths(_collect_input_references_from_runtime_value_surface(step.get("with")), path=base_path + ("with",)))
    nested_steps = step.get("steps")
    if isinstance(nested_steps, list):
        for nested_index, nested_step in enumerate(nested_steps):
            if not isinstance(nested_step, dict):
                continue
            nested_path = base_path + ("steps", str(nested_index))
            references.extend(_iter_input_references_from_nested_step_item(nested_step, path=nested_path))
    if "value" in step:
        references.extend(_pair_input_references_with_paths(_collect_input_references_from_runtime_value_surface(step.get("value")), path=base_path + ("value",)))
    if "profile_switch" in step:
        references.extend(
            _pair_input_references_with_paths(
                _collect_input_references_from_runtime_value_surface(step.get("profile_switch"), allow_bare_strings=False),
                path=base_path + ("profile_switch",),
            )
        )
    if "state_set" in step and isinstance(step.get("state_set"), dict):
        for key, item in step["state_set"].items():
            if isinstance(key, str):
                for reference in _collect_input_references_from_state_path_text(key):
                    references.append((reference, base_path + ("state_set", key)))
                references.extend(
                    _pair_input_references_with_paths(
                        _collect_input_references_from_runtime_value_surface(item, allow_bare_strings=False),
                        path=base_path + ("state_set", key),
                    )
                )
    target_expr = step.get("state_delete")
    if isinstance(target_expr, str):
        for reference in _collect_input_references_from_state_path_text(target_expr):
            references.append((reference, base_path + ("state_delete",)))
    return references


def _iter_input_references_from_nested_step_item(step: JSONObject, *, path: tuple[str, ...]) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    references: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    condition = step.get("if")
    if isinstance(condition, str):
        try:
            parsed = parse_condition_local_expression(condition, context=LocalExpressionContext.STEP_CONDITION)
        except LOCAL_EXPRESSION_PARSE_ERRORS:
            parsed = None
        if parsed is not None and parsed.value is not None:
            for reference in _collect_value_input_references(parsed.value.root):
                references.append((reference, path + ("if",)))
    if "uses" in step or "run" in step:
        references.extend(_pair_input_references_with_paths(_collect_input_references_from_runtime_value_surface(step.get("with")), path=path + ("with",)))
    if "for_each" in step:
        references.extend(_pair_input_references_with_paths(_collect_input_references_from_runtime_value_surface(step.get("for_each")), path=path + ("for_each",)))
    if "value" in step:
        references.extend(_pair_input_references_with_paths(_collect_input_references_from_runtime_value_surface(step.get("value")), path=path + ("value",)))
    if "profile_switch" in step:
        references.extend(_pair_input_references_with_paths(_collect_input_references_from_runtime_value_surface(step.get("profile_switch"), allow_bare_strings=False), path=path + ("profile_switch",)))
    if "state_set" in step and isinstance(step.get("state_set"), dict):
        for key, item in step["state_set"].items():
            if not isinstance(key, str):
                continue
            for reference in _collect_input_references_from_state_path_text(key):
                references.append((reference, path + ("state_set", key)))
            references.extend(_pair_input_references_with_paths(_collect_input_references_from_runtime_value_surface(item, allow_bare_strings=False), path=path + ("state_set", key)))
    target_expr = step.get("state_delete")
    if isinstance(target_expr, str):
        for reference in _collect_input_references_from_state_path_text(target_expr):
            references.append((reference, path + ("state_delete",)))
    return references


def _pair_input_references_with_paths(
    references: set[tuple[str, ...]], *, path: tuple[str, ...]
) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    return [(reference, path) for reference in references]


def _collect_input_references_from_runtime_value_surface(value: JSONValue | None, *, allow_bare_strings: bool = True) -> set[tuple[str, ...]]:
    references: set[tuple[str, ...]] = set()
    if _is_format_value_object(value):
        for arg in value.get("args", []):
            references.update(_collect_input_references_from_runtime_value_surface(arg, allow_bare_strings=allow_bare_strings))
        return references
    if isinstance(value, list):
        for item in value:
            references.update(_collect_input_references_from_runtime_value_surface(item, allow_bare_strings=allow_bare_strings))
        return references
    if isinstance(value, dict):
        for item in value.values():
            references.update(_collect_input_references_from_runtime_value_surface(item, allow_bare_strings=allow_bare_strings))
        return references
    if not isinstance(value, str):
        return references
    mode = _runtime_value_expression_mode(value, allow_bare_strings=allow_bare_strings)
    if mode is None:
        return references
    try:
        parsed = parse_embedded_value_local_expression(value) if mode == "embedded" else parse_value_local_expression(value)
    except LOCAL_EXPRESSION_PARSE_ERRORS:
        return references
    if parsed is None or parsed.value is None:
        return references
    return _collect_value_input_references(parsed.value.root)


def _collect_input_references_from_state_path_text(value: str) -> set[tuple[str, ...]]:
    try:
        parsed = parse_state_path(value)
    except StatePathParseError:
        return set()
    return {parsed.key_reference}


def _validate_state_role_write_order(payload: JSONObject, *, source: str) -> list[Diagnostic]:
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return []

    events: list[tuple[int, str, str, tuple[str, ...]]] = []
    position = 0
    for block_index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        if isinstance(block.get("guards"), list):
            for guard_index, guard in enumerate(block["guards"]):
                for role in _collect_state_roles_from_guard_item(guard):
                    events.append((position, role, "read", ("blocks", str(block_index), "guards", str(guard_index))))
                position += 1
            continue
        if not isinstance(block.get("steps"), list):
            continue
        for step_index, step in enumerate(block["steps"]):
            if not isinstance(step, dict):
                position += 1
                continue
            step_path = ("blocks", str(block_index), "steps", str(step_index))
            for role in _collect_state_roles_from_step_item(step):
                events.append((position, role, "read", step_path))
            target_role = _state_target_role_from_step_item(step)
            if target_role is not None:
                events.append((position, target_role, "write", step_path))
            position += 1

    last_reads: dict[str, int] = {}
    for event_index, role, kind, _ in events:
        if kind == "read":
            last_reads[role] = event_index

    diagnostics: list[Diagnostic] = []
    for event_index, role, kind, path in events:
        if kind != "write":
            continue
        last_read = last_reads.get(role)
        if last_read is None or event_index >= last_read:
            continue
        diagnostics.append(
            _diagnostic(
                "validation.workflow.state_role.write_before_last_read",
                "Logical state role writes and deletes are allowed only after the final read of that same role",
                path,
                source,
                state_role=role,
            )
        )
    return diagnostics


def _validate_block_list(value: JSONValue | None, *, source: str, let_bindings: JSONObject) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.workflow.blocks.type", "Field 'blocks' must be a list", ("blocks",), source, actual_type=type(value).__name__))
        return diagnostics

    declared_registers = _collect_declared_registers_from_blocks(value)
    seen_registers: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(value):
        path = ("blocks", str(index))
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("validation.workflow.block.type", "Block entry must be an object", path, source, actual_type=type(item).__name__))
            continue
        diagnostics.extend(_validate_unknown_fields(item, BLOCK_ALLOWED_FIELDS, path=path, source=source))
        has_guards = "guards" in item
        has_steps = "steps" in item
        has_include = "include" in item
        if sum((has_guards, has_steps, has_include)) != 1:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.block.form",
                    "Block must define exactly one of 'guards', 'steps', or 'include'",
                    path,
                    source,
                )
            )
            continue
        if has_guards:
            diagnostics.extend(_validate_unknown_fields(item, frozenset({"guards"}), path=path, source=source))
            diagnostics.extend(_validate_guard_list(item.get("guards"), source=source, path=path + ("guards",), let_bindings=let_bindings))
        elif has_steps:
            diagnostics.extend(_validate_unknown_fields(item, frozenset({"steps"}), path=path, source=source))
            step_path = path + ("steps",)
            diagnostics.extend(
                _validate_step_list(
                    item.get("steps"),
                    source=source,
                    path=step_path,
                    let_bindings=let_bindings,
                    prior_registers=seen_registers,
                    declared_registers=declared_registers,
                )
            )
            seen_registers.update(_collect_declared_registers_from_step_list(item.get("steps"), path=step_path))
        elif has_include:
            diagnostics.extend(_validate_include_block(item, source=source, path=path, let_bindings=let_bindings))
    return diagnostics


def _validate_include_block(value: JSONObject, *, source: str, path: tuple[str, ...], let_bindings: JSONObject) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_validate_unknown_fields(value, frozenset({"include", "with"}), path=path, source=source))
    diagnostics.extend(_require_non_empty_string(value, "include", path=path + ("include",), source=source))
    with_value = value.get("with")
    if with_value is not None and not isinstance(with_value, dict):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.include.with.type",
                "Include field 'with' must be an object when provided",
                path + ("with",),
                source,
                actual_type=type(with_value).__name__,
            )
        )
    elif isinstance(with_value, dict):
        diagnostics.extend(_validate_include_binding_values(with_value, source=source, path=path + ("with",), let_bindings=let_bindings))
    return diagnostics


def _validate_include_binding_values(value: JSONValue, *, source: str, path: tuple[str, ...], let_bindings: JSONObject) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if isinstance(value, list):
        for index, item in enumerate(value):
            diagnostics.extend(_validate_include_binding_values(item, source=source, path=path + (str(index),), let_bindings=let_bindings))
        return diagnostics
    if isinstance(value, dict):
        for key, item in value.items():
            diagnostics.extend(_validate_include_binding_values(item, source=source, path=path + (str(key),), let_bindings=let_bindings))
        return diagnostics
    if not isinstance(value, str):
        return diagnostics
    try:
        parsed = parse_embedded_local_expression(value, context=LocalExpressionContext.INCLUDE_BINDING)
    except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
        expression = _extract_runtime_value_expression(value)
        diagnostics.append(
            build_local_expression_parse_diagnostic(
                exc,
                context=LocalExpressionContext.INCLUDE_BINDING,
                path=path,
                source=source,
                expression="" if expression is None else expression,
            )
        )
        return diagnostics
    if parsed is None:
        return diagnostics
    for validation_error in validate_parsed_local_expression(parsed):
        diagnostics.append(
            build_local_expression_validation_diagnostic(
                validation_error,
                context=LocalExpressionContext.INCLUDE_BINDING,
                path=path,
                source=source,
                expression=_extract_runtime_value_expression(value) or value,
            )
        )
    diagnostics.extend(
        _validate_workflow_let_binding_uses(
            parsed.root,
            source=source,
            path=path,
            context=LocalExpressionContext.INCLUDE_BINDING,
            expression=_extract_runtime_value_expression(value) or value,
            let_bindings=let_bindings,
        )
    )
    return diagnostics


def _collect_declared_registers_from_blocks(value: list[JSONValue]) -> dict[str, tuple[str, ...]]:
    declared_registers: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(value):
        if not isinstance(item, dict) or "steps" not in item:
            continue
        declared_registers.update(_collect_declared_registers_from_step_list(item.get("steps"), path=("blocks", str(index), "steps")))
    return declared_registers


def _collect_declared_registers_from_step_list(value: JSONValue | None, *, path: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, list):
        return {}
    return {
        item["register"]: path + (str(index), "register")
        for index, item in enumerate(value)
        if isinstance(item, dict)
        and ("uses" in item or "run" in item or ("steps" in item and "for_each" in item) or "value" in item)
        and isinstance(item.get("register"), str)
        and REGISTER_PATTERN.fullmatch(item["register"])
    }


def validate_profile_document(payload: JSONValue, *, source: str = "<memory>") -> ValidationReport:
    """Validate canonical JSON-shaped profile data."""

    diagnostics: list[Diagnostic] = []

    if not isinstance(payload, dict):
        diagnostics.append(_diagnostic("validation.profile.root_type", "Profile root must be an object", (), source, actual_type=type(payload).__name__))
        return ValidationReport(document_kind="profile", status=RuntimeStatus.VALIDATION_ERROR, diagnostics=tuple(diagnostics))

    diagnostics.extend(_validate_unknown_fields(payload, PROFILE_ALLOWED_FIELDS, path=(), source=source))
    diagnostics.extend(_require_non_empty_string(payload, "name", source=source))
    diagnostics.extend(_require_object_field(payload, "inputs", source=source, required=False))
    if "working_directory" in payload:
        diagnostics.extend(_require_non_empty_string(payload, "working_directory", source=source, path=("working_directory",)))
    diagnostics.extend(_validate_connector_context_field(payload.get("connectors"), path=("connectors",), source=source))
    diagnostics.extend(_validate_checks(payload.get("checks"), source=source))
    diagnostics.extend(_validate_overrides(payload.get("overrides"), source=source))
    diagnostics.extend(_validate_launchers(payload.get("launchers"), source=source))

    return _report("profile", diagnostics)


def validate_workflow_semantics(
    workflow: Workflow,
    *,
    source: str | None = None,
    routine_registry: RoutineRegistry | None = None,
) -> ValidationReport:
    """Validate shared post-assembly workflow semantics for all runtime entrypoints."""

    effective_source = source or workflow.source_path or "<memory>"
    document_report = validate_workflow_document(workflow.to_contract(), source=effective_source)
    diagnostics = list(document_report.diagnostics)
    if document_report.ok:
        diagnostics.extend(validate_workflow_run_target_inputs(workflow))
        effective_registry = routine_registry
        if effective_registry is None and workflow_uses_routine(workflow):
            try:
                effective_registry = load_workflow_routine_registry(workflow)
            except RoutineRegistryError as exc:
                diagnostics.extend(exc.diagnostics)
        if effective_registry is not None:
            diagnostics.extend(validate_workflow_routine_invocations(workflow, effective_registry))
        diagnostics.extend(_warn_on_routine_exception_path_usage(workflow, source=effective_source))
    return _report("workflow", diagnostics)


def validate_workflow_run_target_inputs(workflow: Workflow) -> tuple[Diagnostic, ...]:
    """Validate undeclared root-input references across reusable run targets."""

    diagnostics: list[Diagnostic] = []
    _validate_workflow_run_target_inputs_recursive(workflow, diagnostics=diagnostics, visited_paths=set())
    return tuple(diagnostics)


def _validate_workflow_run_target_inputs_recursive(
    workflow: Workflow,
    *,
    diagnostics: list[Diagnostic],
    visited_paths: set[str],
) -> None:
    for block_index, block in enumerate(workflow.blocks):
        if not isinstance(block, StepBlock):
            continue
        for step_index, step in enumerate(block.steps):
            if step.run is None or step.resolved_run_path is None:
                continue
            run_path = str(Path(step.resolved_run_path).resolve())
            if run_path in visited_paths:
                continue
            visited_paths.add(run_path)
            nested = _load_run_target_workflow_for_validation(step=step, workflow=workflow, block_index=block_index, step_index=step_index)
            if isinstance(nested, Diagnostic):
                diagnostics.append(nested)
                continue
            diagnostics.extend(validate_workflow_document(nested.to_contract(), source=nested.source_path or run_path).diagnostics)
            _validate_workflow_run_target_inputs_recursive(nested, diagnostics=diagnostics, visited_paths=visited_paths)


def _load_run_target_workflow_for_validation(
    *,
    step,
    workflow: Workflow,
    block_index: int,
    step_index: int,
) -> Workflow | Diagnostic:
    assert step.run is not None
    assert step.resolved_run_path is not None
    run_path = Path(step.resolved_run_path)
    launch_dir = Path(workflow.launch_dir) if workflow.launch_dir is not None else run_path.parent
    node_path = ("blocks", str(block_index), "steps", str(step_index), "run")
    payload = load_run_target_payload(
        run_path=run_path,
        launch_dir=launch_dir,
        bindings=_sanitize_run_validation_bindings(step.run_with, include_iteration_item=step.for_each is not None),
        node_path=node_path,
    )
    if isinstance(payload, Diagnostic):
        return payload
    built = build_run_target_workflow(
        payload,
        caller_workflow=workflow,
        step=step,
        run_path=run_path,
        launch_dir=launch_dir,
        node_path=node_path,
    )
    if isinstance(built, Diagnostic) and built.code == "runtime.run.fragment_shape":
        return _diagnostic(
            "validation.workflow.run.fragment_shape",
            "Run fragment must normalize to workflow block content",
            node_path,
            workflow.source_path or "<memory>",
            reference=step.run,
            actual_type=built.details.get("actual_type"),
        )
    return built


def _sanitize_run_validation_bindings(bindings: JSONObject, *, include_iteration_item: bool) -> JSONObject:
    sanitized = {key: _sanitize_run_validation_binding_value(value) for key, value in bindings.items()}
    if include_iteration_item and "item" not in sanitized:
        sanitized["item"] = "__ordo_run_item__"
    return sanitized


def _sanitize_run_validation_binding_value(value: JSONValue) -> JSONValue:
    if isinstance(value, str):
        expression = _extract_runtime_value_expression(value)
        if expression is None and value and authored_string_style(value) == "plain":
            return "__ordo_run_binding__"
        if expression is not None:
            return "__ordo_run_binding__"
        return value
    return value


def _validate_guard_list(value: JSONValue | None, *, source: str, path: tuple[str, ...] = ("guards",), let_bindings: JSONObject) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.workflow.guards.type", "Field 'guards' must be a list", path, source, actual_type=type(value).__name__))
        return diagnostics

    for index, item in enumerate(value):
        item_path = path + (str(index),)
        if isinstance(item, str):
            if not item:
                diagnostics.append(_diagnostic("validation.workflow.local_expression.guard.empty", "Guard expression must not be empty", item_path, source))
                continue
            try:
                parsed = parse_local_expression(item, context=LocalExpressionContext.GUARD)
            except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
                diagnostics.append(
                    build_local_expression_parse_diagnostic(
                        exc,
                        context=LocalExpressionContext.GUARD,
                        path=item_path,
                        source=source,
                        expression=item,
                    )
                )
                continue
            for validation_error in validate_parsed_local_expression(parsed):
                diagnostics.append(
                    build_local_expression_validation_diagnostic(
                        validation_error,
                        context=LocalExpressionContext.GUARD,
                        path=item_path,
                        source=source,
                        expression=item,
                    )
                )
            diagnostics.extend(
                _validate_workflow_let_binding_uses(
                    parsed.root,
                    source=source,
                    path=item_path,
                    context=LocalExpressionContext.GUARD,
                    expression=item,
                    let_bindings=let_bindings,
                )
            )
            continue
        if isinstance(item, dict) and "uses" in item:
            diagnostics.append(
                _warning(
                    "validation.workflow.local_expression.guard.uses_deprecated",
                    "Object-form guard 'uses:' entries are compatibility-only; prefer native guard expressions",
                    item_path + ("uses",),
                    source,
                )
            )
            if isinstance(item.get("uses"), str) and item.get("uses", "").startswith(ROUTINE_REFERENCE_PREFIX):
                diagnostics.append(
                    _diagnostic(
                        "validation.workflow.guard.routine_forbidden",
                        "Routine invocations are not allowed in guard blocks",
                        item_path + ("uses",),
                        source,
                    )
                )
        diagnostics.extend(_validate_call(item, path=item_path, source=source))
    return diagnostics


def _validate_step_list(
    value: JSONValue | None,
    *,
    source: str,
    path: tuple[str, ...] = ("steps",),
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
    inherit_prior_register_names: bool = True,
    extra_condition_roots: frozenset[str] = frozenset(),
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.workflow.steps.type", "Field 'steps' must be a list", path, source, actual_type=type(value).__name__))
        return diagnostics

    seen_names: dict[str, tuple[str, ...]] = {}
    seen_registers = {} if prior_registers is None or not inherit_prior_register_names else dict(prior_registers)
    effective_declared_registers = declared_registers if declared_registers is not None else _collect_declared_registers_from_step_list(value, path=path)
    for index, item in enumerate(value):
        item_path = path + (str(index),)
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("validation.workflow.step.type", "Step entry must be an object", item_path, source, actual_type=type(item).__name__))
            continue

        diagnostics.extend(_validate_unknown_fields(item, STEP_ALLOWED_FIELDS, path=item_path, source=source))
        diagnostics.extend(_require_non_empty_string(item, "name", path=item_path + ("name",), source=source))
        has_uses = "uses" in item
        has_run = "run" in item
        has_inline_steps = "steps" in item
        has_profile_switch = "profile_switch" in item
        has_value = "value" in item
        has_result = "result" in item
        has_publish = "publish" in item
        has_state_set = "state_set" in item
        has_state_delete = "state_delete" in item
        form_count = sum((has_uses, has_run, has_inline_steps, has_profile_switch, has_value, has_result, has_publish, has_state_set, has_state_delete))

        prior_registers = {name: register_path for name, register_path in seen_registers.items()}

        if form_count != 1:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.form",
                    "Step must define exactly one of 'uses', 'run', 'steps', 'profile_switch', 'value', 'result', 'publish', 'state_set', or 'state_delete'",
                    item_path,
                    source,
                )
            )
        elif has_uses:
            diagnostics.extend(
                _validate_call(
                    item,
                    path=item_path,
                    source=source,
                    allowed_fields=STEP_ALLOWED_FIELDS,
                    let_bindings=let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        elif has_run:
            diagnostics.extend(
                _validate_run_step(
                    item,
                    source=source,
                    path=item_path,
                    let_bindings=let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        elif has_inline_steps:
            diagnostics.extend(
                _validate_inline_invocation_step(
                    item,
                    source=source,
                    path=item_path,
                    let_bindings=let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        elif has_profile_switch:
            diagnostics.extend(
                _validate_profile_switch_step(
                    item,
                    source=source,
                    path=item_path,
                    let_bindings=let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        elif has_value:
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item.get("value"),
                    path=item_path + ("value",),
                    source=source,
                    let_bindings=let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        elif has_result:
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item.get("result"),
                    path=item_path + ("result",),
                    source=source,
                    let_bindings=let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        elif has_publish:
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item.get("publish"),
                    path=item_path + ("publish",),
                    source=source,
                    let_bindings=let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        if "for_each" in item and not (has_run or has_inline_steps):
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.for_each_without_invocation_body",
                    "Step field 'for_each' is allowed only together with 'run' or inline 'steps'",
                    item_path + ("for_each",),
                    source,
                )
            )
        if "with" in item and not (has_uses or has_run):
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.with_without_uses",
                    "Step field 'with' is allowed only together with 'uses' or 'run'",
                    item_path + ("with",),
                    source,
                )
            )

        diagnostics.extend(
                _validate_step_condition(
                    item,
                    path=item_path,
                    source=source,
                    let_bindings=let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                    extra_allowed_reference_roots=extra_condition_roots,
                )
            )
        diagnostics.extend(_validate_step_launcher(item, path=item_path, source=source, can_use_launcher=has_uses))
        diagnostics.extend(_validate_step_register(item, path=item_path, source=source, can_register=has_uses or has_run or has_inline_steps or has_value))

        if has_state_set:
            diagnostics.extend(_require_object_field(item, "state_set", path=item_path + ("state_set",), source=source, required=True))
            diagnostics.extend(
                _validate_state_set_shape(
                    item.get("state_set"),
                    path=item_path + ("state_set",),
                    source=source,
                    let_bindings=let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        if has_state_delete:
            diagnostics.extend(_require_non_empty_string(item, "state_delete", path=item_path + ("state_delete",), source=source))
            diagnostics.extend(_validate_state_path_text(item.get("state_delete"), path=item_path + ("state_delete",), source=source))

        name = item.get("name")
        if isinstance(name, str) and name:
            if name in seen_names:
                diagnostics.append(_diagnostic("validation.workflow.step.duplicate_name", f"Duplicate step name '{name}'", item_path + ("name",), source, first_seen_path=list(seen_names[name])))
            else:
                seen_names[name] = item_path + ("name",)

        register = item.get("register")
        if isinstance(register, str) and register and (has_uses or has_run or has_inline_steps or has_value) and REGISTER_PATTERN.fullmatch(register):
            if register in seen_registers:
                diagnostics.append(
                    _diagnostic(
                        "validation.workflow.step.duplicate_register",
                        f"Duplicate step register '{register}'",
                        item_path + ("register",),
                        source,
                        first_seen_path=list(seen_registers[register]),
                    )
                )
            else:
                seen_registers[register] = item_path + ("register",)

    return diagnostics


def _validate_step_condition(
    value: JSONObject,
    *,
    path: tuple[str, ...],
    source: str,
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
    extra_allowed_reference_roots: frozenset[str] = frozenset(),
) -> list[Diagnostic]:
    return _validate_invocation_condition(
        value,
        path=path,
        source=source,
        let_bindings=let_bindings,
        prior_registers={} if prior_registers is None else prior_registers,
        declared_registers={} if declared_registers is None else declared_registers,
        field_name="if",
        type_code="validation.workflow.step.if.type",
        expression_code="validation.workflow.local_expression.step_condition.syntax",
        type_message="Step field 'if' must be a string-form local expression",
        expression_message="Step field 'if' must be a valid step-condition expression",
        extra_allowed_reference_roots=extra_allowed_reference_roots,
    )


def _validate_invocation_condition(
    value: JSONObject,
    *,
    path: tuple[str, ...],
    source: str,
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]],
    declared_registers: dict[str, tuple[str, ...]],
    field_name: str,
    type_code: str,
    expression_code: str,
    type_message: str,
    expression_message: str,
    extra_allowed_reference_roots: frozenset[str] = frozenset(),
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    condition = value.get(field_name)
    if condition is None:
        return diagnostics
    condition_path = path + (field_name,)
    if not isinstance(condition, str):
        diagnostics.append(_diagnostic(type_code, type_message, condition_path, source, actual_type=type(condition).__name__))
        return diagnostics
    try:
        parsed = parse_condition_local_expression(condition, context=LocalExpressionContext.STEP_CONDITION)
    except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
        expression = _extract_runtime_value_expression(condition)
        diagnostics.append(
            build_local_expression_parse_diagnostic(
                exc,
                context=LocalExpressionContext.STEP_CONDITION,
                path=condition_path,
                source=source,
                expression=condition if expression is None else expression,
            )
        )
        return diagnostics
    expression = _extract_runtime_value_expression(condition)
    diagnostics.extend(
        _validate_step_references(
            collect_step_references(parsed.root),
            path=condition_path,
            source=source,
            prior_registers=prior_registers,
            declared_registers=declared_registers,
        )
    )
    diagnostics.extend(
        _validate_step_condition_type(
            parsed.root,
            path=condition_path,
            source=source,
            let_bindings=let_bindings,
            extra_allowed_reference_roots=extra_allowed_reference_roots,
        )
    )
    diagnostics.extend(
        _validate_workflow_let_binding_uses(
            parsed.root,
            source=source,
            path=condition_path,
            context=LocalExpressionContext.STEP_CONDITION,
            expression=condition if expression is None else expression,
            let_bindings=let_bindings,
        )
    )
    if expression is not None and not any(diagnostic.level == "error" for diagnostic in diagnostics):
        diagnostics.append(
            _warning(
                "validation.workflow.local_expression.step_condition.embedded_if_deprecated",
                "Embedded step 'if: ${...}' is deprecated; prefer a bare step-condition expression",
                condition_path,
                source,
            )
        )
    return diagnostics


def _validate_step_register(value: JSONObject, *, path: tuple[str, ...], source: str, can_register: bool) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    register = value.get("register")
    if register is None:
        return diagnostics
    if not can_register:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.register_without_uses",
                "Step field 'register' is allowed only together with 'uses', 'run', or 'value'",
                path + ("register",),
                source,
            )
        )
        return diagnostics
    if not isinstance(register, str):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.register.type",
                "Step field 'register' must be a string",
                path + ("register",),
                source,
                actual_type=type(register).__name__,
            )
        )
        return diagnostics
    if not register:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.register.empty",
                "Step field 'register' must not be empty",
                path + ("register",),
                source,
            )
        )
        return diagnostics
    if not REGISTER_PATTERN.fullmatch(register):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.register.pattern",
                "Step register must match the stable workflow register pattern",
                path + ("register",),
                source,
                pattern=REGISTER_PATTERN.pattern,
            )
        )
    return diagnostics


def _validate_run_step(
    value: JSONObject,
    *,
    source: str,
    path: tuple[str, ...],
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]],
    declared_registers: dict[str, tuple[str, ...]],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_require_non_empty_string(value, "run", path=path + ("run",), source=source))
    with_value = value.get("with")
    if with_value is not None and not isinstance(with_value, dict):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.run.with.type",
                "Run field 'with' must be an object when provided",
                path + ("with",),
                source,
                actual_type=type(with_value).__name__,
            )
        )
    diagnostics.extend(
        _validate_invocation_condition(
            value,
            path=path,
            source=source,
            let_bindings=let_bindings,
            prior_registers=prior_registers,
            declared_registers=declared_registers,
            field_name="if",
            type_code="validation.workflow.run.if.type",
            expression_code="validation.workflow.run.if.expression",
            type_message="Run field 'if' must be a string-form value expression",
            expression_message="Run field 'if' must use the '${...}' local-expression form",
        )
    )
    if "for_each" in value:
        diagnostics.extend(
            _validate_runtime_value_surface(
                value.get("for_each"),
                path=path + ("for_each",),
                source=source,
                let_bindings=let_bindings,
                prior_registers=prior_registers,
                declared_registers=declared_registers,
            )
        )
    if value.get("register") is not None:
        diagnostics.extend(_validate_step_register(value, path=path, source=source, can_register=True))
    if value.get("launcher") is not None:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.run.launcher_unsupported",
                "Run steps do not support 'launcher' in the MVP",
                path + ("launcher",),
                source,
            )
        )
    return diagnostics


def _validate_inline_invocation_step(
    value: JSONObject,
    *,
    source: str,
    path: tuple[str, ...],
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]] | None,
    declared_registers: dict[str, tuple[str, ...]],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    nested_steps = value.get("steps")
    if not isinstance(nested_steps, list):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.inline_steps.type",
                "Step field 'steps' must be a list when used as an inline repeated body",
                path + ("steps",),
                source,
                actual_type=type(nested_steps).__name__,
            )
        )
        return diagnostics
    if not nested_steps:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.inline_steps.empty",
                "Inline repeated step bodies must contain at least one step",
                path + ("steps",),
                source,
            )
        )
    if "for_each" not in value:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.inline_steps_without_for_each",
                "Inline repeated step bodies require 'for_each'",
                path + ("steps",),
                source,
            )
        )
    else:
        diagnostics.extend(
            _validate_runtime_value_surface(
                value.get("for_each"),
                path=path + ("for_each",),
                source=source,
                let_bindings=let_bindings,
                prior_registers={} if prior_registers is None else prior_registers,
                declared_registers=declared_registers,
            )
        )
    if "with" in value:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.inline_steps.with_forbidden",
                "Inline repeated step bodies do not support outer 'with' bindings",
                path + ("with",),
                source,
            )
        )
    for nested_index, nested_step in enumerate(nested_steps):
        nested_path = path + ("steps", str(nested_index))
        if isinstance(nested_step, dict) and "for_each" in nested_step:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.inline_steps.nested_for_each_forbidden",
                    "Nested 'for_each' is not allowed inside inline repeated step bodies",
                    nested_path + ("for_each",),
                    source,
                )
            )
        if isinstance(nested_step, dict) and "guards" in nested_step:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.inline_steps.nested_guards_forbidden",
                    "Nested guard declarations are not allowed inside inline repeated step bodies",
                    nested_path + ("guards",),
                    source,
                )
            )
    local_declared_registers = _collect_declared_registers_from_step_list(nested_steps, path=path + ("steps",))
    combined_declared_registers = {**declared_registers, **local_declared_registers}
    diagnostics.extend(
        _validate_step_list(
            nested_steps,
            source=source,
            path=path + ("steps",),
            let_bindings=let_bindings,
            prior_registers={} if prior_registers is None else prior_registers,
            declared_registers=combined_declared_registers,
            inherit_prior_register_names=False,
            extra_condition_roots=frozenset({"item"}),
        )
    )
    return diagnostics


def _validate_profile_switch_step(
    value: JSONObject,
    *,
    source: str,
    path: tuple[str, ...],
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]],
    declared_registers: dict[str, tuple[str, ...]],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(
        _validate_profile_switch_value(
            value.get("profile_switch"),
            path=path + ("profile_switch",),
            source=source,
            let_bindings=let_bindings,
            prior_registers=prior_registers,
            declared_registers=declared_registers,
        )
    )
    if value.get("register") is not None:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.profile_switch.register_unsupported",
                "profile_switch steps do not support 'register'",
                path + ("register",),
                source,
            )
        )
    if value.get("launcher") is not None:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.profile_switch.launcher_unsupported",
                "profile_switch steps do not support 'launcher'",
                path + ("launcher",),
                source,
            )
        )
    if value.get("with") is not None:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.profile_switch.with_unsupported",
                "profile_switch steps do not support 'with'",
                path + ("with",),
                source,
            )
        )
    return diagnostics


def _validate_call(
    value: JSONValue,
    *,
    path: tuple[str, ...],
    source: str,
    allowed_fields: frozenset[str] = CALL_ALLOWED_FIELDS,
    let_bindings: JSONObject | None = None,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, dict):
        diagnostics.append(_diagnostic("validation.workflow.call.type", "Operation entry must be an object", path, source, actual_type=type(value).__name__))
        return diagnostics

    if allowed_fields is CALL_ALLOWED_FIELDS:
        diagnostics.extend(_validate_unknown_fields(value, CALL_ALLOWED_FIELDS, path=path, source=source))

    diagnostics.extend(_require_non_empty_string(value, "uses", path=path + ("uses",), source=source, pattern=USES_PATTERN, pattern_message="Operation reference must match the stable connector operation pattern"))
    diagnostics.extend(_require_object_field(value, "with", path=path + ("with",), source=source, required=False))
    with_payload = value.get("with")
    uses_value = value.get("uses")
    if isinstance(uses_value, str) and uses_value.startswith(ROUTINE_REFERENCE_PREFIX):
        diagnostics.extend(_validate_routine_reference_shape(uses_value, path=path + ("uses",), source=source))
    if isinstance(with_payload, dict):
        if isinstance(uses_value, str) and uses_value.startswith(ROUTINE_REFERENCE_PREFIX):
            diagnostics.extend(
                _validate_routine_call_shape_with_context(
                    with_payload,
                    path=path + ("with",),
                    source=source,
                    let_bindings={} if let_bindings is None else let_bindings,
                    prior_registers=prior_registers,
                    declared_registers=declared_registers,
                )
            )
        diagnostics.extend(
            _validate_runtime_value_surface(
                with_payload,
                path=path + ("with",),
                source=source,
                let_bindings={} if let_bindings is None else let_bindings,
                prior_registers=prior_registers,
                declared_registers=declared_registers,
            )
        )
    return diagnostics


def _validate_routine_call_shape(value: JSONObject, *, path: tuple[str, ...], source: str) -> list[Diagnostic]:
    return _validate_routine_call_shape_with_context(value, path=path, source=source, let_bindings={}, prior_registers=None, declared_registers=None)


def _validate_routine_call_shape_with_context(
    value: JSONObject,
    *,
    path: tuple[str, ...],
    source: str,
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]] | None,
    declared_registers: dict[str, tuple[str, ...]] | None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_validate_unknown_fields(value, frozenset({"args", "env"}), path=path, source=source))
    diagnostics.extend(_require_object_field(value, "args", path=path + ("args",), source=source, required=False))
    diagnostics.extend(_require_list_field(value, "env", path=path + ("env",), source=source, required=False))
    env_payload = value.get("env")
    if isinstance(env_payload, list):
        for index, reference in enumerate(env_payload):
            env_path = path + ("env", str(index))
            if not isinstance(reference, str):
                diagnostics.append(
                    _diagnostic(
                        "validation.workflow.routine.env_reference_type",
                        "Routine env entries must be string references",
                        env_path,
                        source,
                        actual_type=type(reference).__name__,
                    )
                )
                continue
            if not ROUTINE_ENV_REFERENCE_PATTERN.fullmatch(reference):
                diagnostics.append(
                    _diagnostic(
                        "validation.workflow.routine.env_reference_pattern",
                        f"Routine env reference '{reference}' must use a supported reference path",
                        env_path,
                        source,
                        reference=reference,
                        pattern=ROUTINE_ENV_REFERENCE_PATTERN.pattern,
                    )
                )
                continue
            diagnostics.extend(
                _validate_runtime_value_surface(
                    f"${{{reference}}}",
                    path=env_path,
                    source=source,
                    let_bindings=let_bindings,
                    allow_bare_strings=True,
                    prior_registers=prior_registers,
                    declared_registers=declared_registers,
                )
            )
    return diagnostics


def _validate_routine_reference_shape(value: str, *, path: tuple[str, ...], source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if parse_routine_reference(value) is None:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.routine.reference",
                "Routine references must use the form 'routine.<id>' with a non-empty published routine id",
                path,
                source,
                reference=value,
            )
        )
    return diagnostics


def _warn_on_routine_exception_path_usage(workflow: Workflow, *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for block_index, block in enumerate(workflow.blocks):
        if not isinstance(block, StepBlock):
            continue
        for step_index, step in enumerate(block.steps):
            if step.operation is None:
                continue
            routine_id = parse_routine_reference(step.operation.uses)
            if routine_id is None:
                continue
            diagnostics.append(
                _warning(
                    "validation.workflow.routine.exception_path",
                    f"Routine '{routine_id}' is a constrained exception path; prefer richer connector or composed public surfaces when available",
                    ("blocks", str(block_index), "steps", str(step_index), "uses"),
                    source,
                    routine_id=routine_id,
                )
            )
    return diagnostics


def _validate_state_set_shape(
    value: JSONValue | None,
    *,
    path: tuple[str, ...],
    source: str,
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, dict):
        return diagnostics
    if len(value) != 1:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.state_set.entry_count",
                "Field 'state_set' must contain exactly one target entry",
                path,
                source,
                actual_count=len(value),
            )
        )
    for key in value:
        if not isinstance(key, str) or not key:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.state_set.target_type",
                    "State set target must be a non-empty string",
                    path,
                    source,
                    actual_type=type(key).__name__,
                )
            )
            continue
        diagnostics.extend(_validate_state_path_text(key, path=path + (key,), source=source))
    for key, item in value.items():
        if isinstance(key, str):
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item,
                    path=path + (key,),
                    source=source,
                    let_bindings=let_bindings,
                    allow_bare_strings=False,
                    prior_registers=prior_registers,
                    declared_registers=declared_registers,
                )
            )
    return diagnostics


def _validate_runtime_value_surface(
    value: JSONValue | None,
    *,
    path: tuple[str, ...],
    source: str,
    let_bindings: JSONObject,
    allow_bare_strings: bool = True,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = collect_static_expression_diagnostics(value, path=path, source=source)
    if _is_format_value_object(value):
        diagnostics.extend(
            _validate_format_value_object(
                value,
                path=path,
                source=source,
                let_bindings=let_bindings,
                prior_registers=prior_registers,
                declared_registers=declared_registers,
            )
        )
        return diagnostics
    if isinstance(value, list):
        for index, item in enumerate(value):
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item,
                    path=path + (str(index),),
                    source=source,
                    let_bindings=let_bindings,
                    allow_bare_strings=allow_bare_strings,
                    prior_registers=prior_registers,
                    declared_registers=declared_registers,
                )
            )
        return diagnostics
    if isinstance(value, dict):
        for key, item in value.items():
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item,
                    path=path + (str(key),),
                    source=source,
                    let_bindings=let_bindings,
                    allow_bare_strings=allow_bare_strings,
                    prior_registers=prior_registers,
                    declared_registers=declared_registers,
                )
            )
        return diagnostics
    if not isinstance(value, str):
        return diagnostics
    authored_style = authored_string_style(value)
    mode = _runtime_value_expression_mode(value, allow_bare_strings=allow_bare_strings)
    if mode is None:
        if authored_style in {"single", "double", "other"}:
            diagnostics.extend(_validate_quoted_literal_expression_hint(value, path=path, source=source))
        return diagnostics
    try:
        parsed = parse_embedded_value_local_expression(value) if mode == "embedded" else parse_value_local_expression(value)
    except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
        diagnostics.extend(_build_runtime_value_surface_parse_diagnostics(value, path=path, source=source, exc=exc, mode=mode))
        return diagnostics
    if parsed is None or parsed.value is None:
        return diagnostics
    expression = _runtime_value_expression_text(value, mode=mode)
    if mode == "embedded" and allow_bare_strings and authored_style in {"single", "double", "other"} and not _value_expression_requires_escape(expression):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.value_expr.embedded_escape_unnecessary",
                "This quoted ${...} expression can be authored directly as a bare value. Reserve quoted ${...} only for YAML-hostile expressions that need the explicit escape form.",
                path,
                source,
                expression=expression,
            )
        )
        return diagnostics
    surface_diagnostics = _validate_step_references(
        collect_step_references(parsed.value.root),
        path=path,
        source=source,
        prior_registers={} if prior_registers is None else prior_registers,
        declared_registers={} if declared_registers is None else declared_registers,
    )
    root_diagnostics = _validate_runtime_value_reference_roots(parsed.value.root, path=path, source=source, let_bindings=let_bindings)
    surface_diagnostics.extend(root_diagnostics)
    diagnostics.extend(surface_diagnostics)
    for validation_error in validate_parsed_local_expression(parsed):
        diagnostic = build_local_expression_validation_diagnostic(
            validation_error,
            context=LocalExpressionContext.EMBEDDED_VALUE,
            path=path,
            source=source,
            expression=expression,
        )
        diagnostics.append(diagnostic)
        surface_diagnostics.append(diagnostic)
    let_diagnostics = _validate_workflow_let_binding_uses(
        parsed.value.root,
        source=source,
        path=path,
        context=LocalExpressionContext.EMBEDDED_VALUE,
        expression=expression,
        let_bindings=let_bindings,
    )
    diagnostics.extend(let_diagnostics)
    surface_diagnostics.extend(let_diagnostics)
    if mode == "plain" and surface_diagnostics:
        diagnostics.append(
            _warning(
                "validation.workflow.value_expr.literal_string_maybe_unquoted",
                "This bare string may be an intended literal string. Quote it explicitly if it should not be evaluated as an expression.",
                path,
                source,
                expression=value,
                underlying_codes=[diagnostic.code for diagnostic in surface_diagnostics],
            )
        )
    return diagnostics


def _validate_quoted_literal_expression_hint(value: str, *, path: tuple[str, ...], source: str) -> list[Diagnostic]:
    try:
        parsed = parse_value_local_expression(value)
    except LOCAL_EXPRESSION_PARSE_ERRORS:
        return []
    if not _node_looks_like_runtime_expression(parsed.value.root):
        return []
    return [
        _warning(
            "validation.workflow.value_expr.quoted_literal_looks_dynamic",
            "This quoted string looks like a value expression but will be treated as a literal string at runtime. Author it as a bare expression or wrap it in ${...} if evaluation is intended.",
            path,
            source,
            expression=value,
        )
    ]


def _node_looks_like_runtime_expression(node: ValueExpressionNode) -> bool:
    if isinstance(node, (PipelineNode, AdapterInvocationNode, BuiltinCallNode, CallNode, StepReferenceNode, ValueStateReferenceNode)):
        return True
    if isinstance(node, ReferenceNode):
        return bool(node.parts) and node.parts[0] in {"inputs", "args", "item"}
    return False


def _validate_runtime_value_reference_roots(
    node: ValueExpressionNode,
    *,
    path: tuple[str, ...],
    source: str,
    let_bindings: JSONObject,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if isinstance(node, ReferenceNode):
        root = node.parts[0] if node.parts else ""
        if root not in {"inputs", "args", "item"} and not (isinstance(let_bindings, dict) and root in let_bindings):
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.value_expr.root",
                    "Value-bearing workflow surfaces may reference only workflow-local value roots",
                    path,
                    source,
                    root=root,
                )
            )
        return diagnostics
    if isinstance(node, (LiteralNode, ValueStateReferenceNode, StepReferenceNode)):
        return diagnostics
    if isinstance(node, AdapterBindingNode):
        return _validate_runtime_value_reference_roots(node.value, path=path, source=source, let_bindings=let_bindings)
    if isinstance(node, AdapterInvocationNode):
        for binding in node.bindings:
            diagnostics.extend(_validate_runtime_value_reference_roots(binding, path=path, source=source, let_bindings=let_bindings))
        return diagnostics
    if isinstance(node, PipelineNode):
        diagnostics.extend(_validate_runtime_value_reference_roots(node.source, path=path, source=source, let_bindings=let_bindings))
        for filter_node in node.filters:
            diagnostics.extend(_validate_runtime_value_reference_roots(filter_node, path=path, source=source, let_bindings=let_bindings))
        return diagnostics
    if isinstance(node, UnaryNode):
        diagnostics.extend(_validate_runtime_value_reference_roots(node.operand, path=path, source=source, let_bindings=let_bindings))
        return diagnostics
    if isinstance(node, BinaryNode):
        diagnostics.extend(_validate_runtime_value_reference_roots(node.left, path=path, source=source, let_bindings=let_bindings))
        diagnostics.extend(_validate_runtime_value_reference_roots(node.right, path=path, source=source, let_bindings=let_bindings))
        return diagnostics
    if isinstance(node, ListNode):
        for item in node.items:
            diagnostics.extend(_validate_runtime_value_reference_roots(item, path=path, source=source, let_bindings=let_bindings))
        return diagnostics
    if isinstance(node, ObjectNode):
        for entry in node.entries:
            diagnostics.extend(_validate_runtime_value_reference_roots(entry.value, path=path, source=source, let_bindings=let_bindings))
        return diagnostics
    if isinstance(node, BuiltinCallNode):
        for argument in node.arguments:
            diagnostics.extend(_validate_runtime_value_reference_roots(argument, path=path, source=source, let_bindings=let_bindings))
        return diagnostics
    if isinstance(node, CallNode):
        for argument in node.arguments:
            diagnostics.extend(_validate_runtime_value_reference_roots(argument.value, path=path, source=source, let_bindings=let_bindings))
        return diagnostics
    return diagnostics


def _runtime_value_expression_mode(value: str, *, allow_bare_strings: bool) -> str | None:
    style = authored_string_style(value)
    if style in {"single", "double", "other"}:
        return "embedded" if _extract_runtime_value_expression(value) is not None else None
    if style == "plain":
        if _extract_runtime_value_expression(value) is not None:
            return "embedded"
        return "plain" if allow_bare_strings else None
    return "embedded" if _extract_runtime_value_expression(value) is not None else None


def _runtime_value_expression_text(value: str, *, mode: str) -> str:
    if mode == "embedded":
        expression = _extract_runtime_value_expression(value)
        return value if expression is None else expression
    return value


def _build_runtime_value_surface_parse_diagnostics(
    value: str,
    *,
    path: tuple[str, ...],
    source: str,
    exc,
    mode: str,
) -> list[Diagnostic]:
    if mode == "embedded":
        expression = _runtime_value_expression_text(value, mode=mode)
        return [
            build_local_expression_parse_diagnostic(
                exc,
                context=LocalExpressionContext.EMBEDDED_VALUE,
                path=path,
                source=source,
                expression=expression,
            )
        ]
    return [
        _diagnostic(
            "validation.workflow.value_expr.bare_string_invalid",
            "Bare strings in this value surface must be valid expressions. If you intended a literal string, quote it explicitly.",
            path,
            source,
            expression=value,
            position=exc.position,
            end=exc.end if exc.end is not None else exc.position,
            parse_message=exc.message,
        )
    ]


def _value_expression_requires_escape(expression: str) -> bool:
    """Return whether one value expression still needs ${...} to stay YAML-safe.

    Bare-first value surfaces should use plain scalars whenever possible.
    The explicit `${...}` envelope remains available only for expression shapes
    that are not viable as stable YAML plain scalars, such as `with{...}` maps.
    """

    return "with{" in expression


def _validate_profile_switch_value(
    value: JSONValue | None,
    *,
    path: tuple[str, ...],
    source: str,
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]],
    declared_registers: dict[str, tuple[str, ...]],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, str):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.profile_switch.type",
                "profile_switch must be a string literal or a ${...} value expression",
                path,
                source,
                actual_type=type(value).__name__,
            )
        )
        return diagnostics
    if not value:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.profile_switch.empty",
                "profile_switch must not be empty",
                path,
                source,
            )
        )
        return diagnostics
    if authored_string_style(value) == "plain" and _extract_runtime_value_expression(value) is None:
        diagnostics.append(
            _warning(
                "validation.workflow.profile_switch.literal_string_maybe_unquoted",
                "This bare profile_switch value may be an intended literal profile name. Quote it explicitly if it should not be evaluated as an expression.",
                path,
                source,
                expression=value,
            )
        )
    expression = _extract_runtime_value_expression(value)
    if expression is None:
        return diagnostics
    try:
        parsed = parse_embedded_value_local_expression(value)
    except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
        diagnostics.append(
            build_local_expression_parse_diagnostic(
                exc,
                context=LocalExpressionContext.EMBEDDED_VALUE,
                path=path,
                source=source,
                expression=expression,
            )
        )
        return diagnostics
    if parsed is None or parsed.value is None:
        return diagnostics
    references = collect_step_references(parsed.value.root)
    if references:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.profile_switch.step_ref_forbidden",
                "profile_switch must not depend on step.* references",
                path,
                source,
                references=[f"step.{reference.register}" + ("." + ".".join(reference.fields) if reference.fields else "") for reference in references],
            )
        )
        return diagnostics
    diagnostics.extend(
        _validate_runtime_value_surface(
            value,
            path=path,
            source=source,
            let_bindings=let_bindings,
            prior_registers=prior_registers,
            declared_registers=declared_registers,
        )
    )
    return diagnostics


def _validate_workflow_let_binding_uses(
    node: ValueExpressionNode,
    *,
    source: str,
    path: tuple[str, ...],
    context: LocalExpressionContext,
    expression: str,
    let_bindings: JSONObject,
) -> list[Diagnostic]:
    if not isinstance(let_bindings, dict) or not let_bindings:
        return []
    diagnostics: list[Diagnostic] = []
    for binding_name in _collect_direct_let_references(node, let_bindings):
        binding_expression = let_bindings.get(binding_name)
        if not isinstance(binding_expression, str):
            continue
        try:
            parsed_binding = parse_local_expression(
                binding_expression,
                context=context,
                allow_boolean_composition=context in {LocalExpressionContext.GUARD, LocalExpressionContext.STEP_CONDITION},
            )
        except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
            diagnostics.append(
                Diagnostic(
                    code="validation.workflow.let.binding_syntax",
                    level="error",
                    message=f"Workflow let binding '{binding_name}' is not valid in the {context.value} local-expression context",
                    path=path,
                    details={
                        "source": source,
                        "binding_name": binding_name,
                        "binding_path": ["let", binding_name],
                        "binding_expression": binding_expression,
                        "use_expression": expression,
                        "position": exc.position,
                        "end": exc.end if exc.end is not None else exc.position,
                        "parse_message": exc.message,
                    },
                )
            )
            continue
        for validation_error in validate_parsed_local_expression(parsed_binding):
            diagnostic = build_local_expression_validation_diagnostic(
                validation_error,
                context=context,
                path=path,
                source=source,
                expression=binding_expression,
            )
            details = dict(diagnostic.details)
            details.update(
                {
                    "binding_name": binding_name,
                    "binding_path": ["let", binding_name],
                    "binding_expression": binding_expression,
                    "use_expression": expression,
                }
            )
            diagnostics.append(
                Diagnostic(
                    code=diagnostic.code,
                    level=diagnostic.level,
                    message=diagnostic.message,
                    path=diagnostic.path,
                    details=details,
                )
            )
    return diagnostics


def _extract_runtime_value_expression(value: str) -> str | None:
    if value.startswith("${") and value.endswith("}") and len(value) >= 4:
        return value[2:-1]
    return None


def _validate_step_condition_type(
    node: ValueExpressionNode,
    *,
    path: tuple[str, ...],
    source: str,
    let_bindings: JSONObject,
    extra_allowed_reference_roots: frozenset[str] = frozenset(),
) -> list[Diagnostic]:
    inferred, diagnostics = _infer_value_expression_type(
        node,
        path=path,
        source=source,
        step_condition_mode=True,
        let_bindings=let_bindings,
        extra_allowed_reference_roots=extra_allowed_reference_roots,
    )
    if inferred not in {"boolean", "unknown"}:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.if_expr.result_type",
                "Step condition must evaluate to a boolean value",
                path,
                source,
                inferred_type=inferred,
            )
        )
    return diagnostics


def _infer_value_expression_type(
    node: ValueExpressionNode,
    *,
    path: tuple[str, ...],
    source: str,
    step_condition_mode: bool = False,
    let_bindings: JSONObject | None = None,
    extra_allowed_reference_roots: frozenset[str] = frozenset(),
) -> tuple[str, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    if isinstance(node, LiteralNode):
        if isinstance(node.value, bool):
            return "boolean", diagnostics
        if isinstance(node.value, str):
            return "string", diagnostics
        if isinstance(node.value, int):
            return "integer", diagnostics
        if node.value is None:
            return "null", diagnostics
        return "unknown", diagnostics
    if isinstance(node, ReferenceNode):
        if (
            step_condition_mode
            and node.parts[0] != "inputs"
            and node.parts[0] != "item"
            and node.parts[0] not in extra_allowed_reference_roots
            and not (isinstance(let_bindings, dict) and node.parts[0] in let_bindings)
        ):
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.if_expr.root",
                    "Step conditions may reference only workflow-local roots",
                    path,
                    source,
                    root=node.parts[0],
                )
            )
        return "unknown", diagnostics
    if isinstance(node, (ValueStateReferenceNode, StepReferenceNode)):
        return "unknown", diagnostics
    if isinstance(node, BuiltinCallNode):
        if node.name == "format":
            for argument in node.arguments:
                _, argument_diagnostics = _infer_value_expression_type(
                    argument,
                    path=path,
                    source=source,
                    step_condition_mode=step_condition_mode,
                    let_bindings=let_bindings,
                    extra_allowed_reference_roots=extra_allowed_reference_roots,
                )
                diagnostics.extend(argument_diagnostics)
            return "string", diagnostics
        return "unknown", diagnostics
    if isinstance(node, AdapterBindingNode):
        _, binding_diagnostics = _infer_value_expression_type(
            node.value,
            path=path,
            source=source,
            step_condition_mode=step_condition_mode,
            let_bindings=let_bindings,
            extra_allowed_reference_roots=extra_allowed_reference_roots,
        )
        diagnostics.extend(binding_diagnostics)
        return "unknown", diagnostics
    if isinstance(node, AdapterInvocationNode):
        for binding in node.bindings:
            _, binding_diagnostics = _infer_value_expression_type(
                binding,
                path=path,
                source=source,
                step_condition_mode=step_condition_mode,
                let_bindings=let_bindings,
                extra_allowed_reference_roots=extra_allowed_reference_roots,
            )
            diagnostics.extend(binding_diagnostics)
        return "unknown", diagnostics
    if isinstance(node, PipelineNode):
        current_type, diagnostics = _infer_value_expression_type(
            node.source,
            path=path,
            source=source,
            step_condition_mode=step_condition_mode,
            let_bindings=let_bindings,
            extra_allowed_reference_roots=extra_allowed_reference_roots,
        )
        for filter_node in node.filters:
            current_type, filter_diagnostics = _infer_filter_result_type(filter_node, input_type=current_type, path=path, source=source)
            diagnostics.extend(filter_diagnostics)
        return current_type, diagnostics
    if isinstance(node, UnaryNode):
        operand_type, operand_diagnostics = _infer_value_expression_type(
            node.operand,
            path=path,
            source=source,
            step_condition_mode=step_condition_mode,
            let_bindings=let_bindings,
            extra_allowed_reference_roots=extra_allowed_reference_roots,
        )
        diagnostics.extend(operand_diagnostics)
        if operand_type not in {"boolean", "unknown"}:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.if_expr.boolean_operand_type",
                    f"Operator '{node.operator}' requires a boolean operand",
                    path,
                    source,
                    operator=node.operator,
                    actual_type=operand_type,
                )
            )
        return "boolean", diagnostics
    if isinstance(node, BinaryNode):
        left_type, left_diagnostics = _infer_value_expression_type(
            node.left,
            path=path,
            source=source,
            step_condition_mode=step_condition_mode,
            let_bindings=let_bindings,
            extra_allowed_reference_roots=extra_allowed_reference_roots,
        )
        right_type, right_diagnostics = _infer_value_expression_type(
            node.right,
            path=path,
            source=source,
            step_condition_mode=step_condition_mode,
            let_bindings=let_bindings,
            extra_allowed_reference_roots=extra_allowed_reference_roots,
        )
        diagnostics.extend(left_diagnostics)
        diagnostics.extend(right_diagnostics)
        for operand_type in (left_type, right_type):
            if operand_type not in {"boolean", "unknown"}:
                diagnostics.append(
                    _diagnostic(
                        "validation.workflow.step.if_expr.boolean_operand_type",
                        f"Operator '{node.operator}' requires boolean operands",
                        path,
                        source,
                        operator=node.operator,
                        actual_type=operand_type,
                    )
                )
        return "boolean", diagnostics
    return "unknown", diagnostics


def _infer_filter_result_type(
    filter_node: FilterApplicationNode,
    *,
    input_type: str,
    path: tuple[str, ...],
    source: str,
) -> tuple[str, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    spec = VALUE_EXPRESSION_FILTERS.get(filter_node.name)
    if spec is None:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.if_expr.filter_unknown",
                f"Unknown local-expression filter '{filter_node.name}'",
                path,
                source,
                filter=filter_node.name,
            )
        )
        return "unknown", diagnostics
    if len(filter_node.arguments) != spec.argument_count:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.if_expr.filter_args",
                f"Filter '{filter_node.name}' requires exactly {spec.argument_count} argument(s)",
                path,
                source,
                filter=filter_node.name,
                arguments=len(filter_node.arguments),
                expected_arguments=spec.argument_count,
            )
        )
    if filter_node.name in {"lower", "trim", "slug"}:
        if input_type not in {"string", "unknown"}:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.if_expr.filter_type",
                    f"Filter '{filter_node.name}' requires a string input",
                    path,
                    source,
                    filter=filter_node.name,
                    actual_type=input_type,
                )
            )
        return "string", diagnostics
    if filter_node.name in {"eq", "ne", "is_string", "is_number", "is_integer", "is_boolean", "in"}:
        return "boolean", diagnostics
    if filter_node.name == "field":
        if filter_node.arguments and isinstance(filter_node.arguments[0], LiteralNode):
            argument = filter_node.arguments[0]
            if not isinstance(argument.value, str):
                diagnostics.append(
                    _diagnostic(
                        "validation.workflow.step.if_expr.field_path_type",
                        "Filter 'field' requires a string path argument",
                        path,
                        source,
                        filter="field",
                        actual_type=type(argument.value).__name__,
                    )
                )
            else:
                try:
                    _parse_field_path(argument.value)
                except _FieldPathSyntaxError as exc:
                    diagnostics.append(
                        _diagnostic(
                            "validation.workflow.step.if_expr.field_path_invalid",
                            exc.message,
                            path,
                            source,
                            filter="field",
                            field_path=argument.value,
                        )
                    )
        return "unknown", diagnostics
    if filter_node.name == "length":
        return "number", diagnostics
    if filter_node.name in {"only", "flatten", "first", "last", "unique"}:
        return "unknown", diagnostics
    if filter_node.name == "not":
        if input_type not in {"boolean", "unknown"}:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.if_expr.not_type",
                    "Filter 'not' requires a boolean input",
                    path,
                    source,
                    actual_type=input_type,
                )
            )
        return "boolean", diagnostics
    return "unknown", diagnostics


def _is_format_value_object(value: JSONValue | None) -> bool:
    return isinstance(value, dict) and "format" in value


def _validate_format_value_object(
    value: JSONObject,
    *,
    path: tuple[str, ...],
    source: str,
    let_bindings: JSONObject,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    allowed_fields = {"format", "args"}
    for key in value:
        if key not in allowed_fields:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.value_expr.format.unknown_field",
                    f"Unknown local-expression format field '{key}'",
                    path + (key,),
                    source,
                    allowed_fields=sorted(allowed_fields),
                )
            )
    template = value.get("format")
    if not isinstance(template, str):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.value_expr.format.template_type",
                "Field 'format' must be a string",
                path + ("format",),
                source,
                actual_type=type(template).__name__,
            )
        )
    args = value.get("args", [])
    if not isinstance(args, list):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.value_expr.format.args_type",
                "Field 'args' must be a list when provided",
                path + ("args",),
                source,
                actual_type=type(args).__name__,
            )
        )
        return diagnostics
    for index, item in enumerate(args):
        diagnostics.extend(
            _validate_runtime_value_surface(
                item,
                path=path + ("args", str(index)),
                source=source,
                let_bindings=let_bindings,
                prior_registers=prior_registers,
                declared_registers=declared_registers,
            )
        )
    return diagnostics


def _collect_state_roles_from_guard_item(item: JSONValue) -> set[str]:
    if isinstance(item, str):
        try:
            parsed = parse_local_expression(item, context=LocalExpressionContext.GUARD)
        except LOCAL_EXPRESSION_PARSE_ERRORS:
            return set()
        return _collect_value_state_references(parsed.value.root)
    if isinstance(item, dict):
        return _collect_state_roles_from_runtime_value_surface(item.get("with"))
    return set()


def _collect_state_roles_from_step_item(step: JSONObject) -> set[str]:
    roles: set[str] = set()
    condition = step.get("if")
    if isinstance(condition, str):
        try:
            parsed = parse_condition_local_expression(condition, context=LocalExpressionContext.STEP_CONDITION)
        except LOCAL_EXPRESSION_PARSE_ERRORS:
            parsed = None
        if parsed is not None and parsed.value is not None:
            roles.update(_collect_value_state_references(parsed.value.root))
    if "uses" in step or "run" in step:
        roles.update(_collect_state_roles_from_runtime_value_surface(step.get("with")))
    if "value" in step:
        roles.update(_collect_state_roles_from_runtime_value_surface(step.get("value")))
    if "state_set" in step and isinstance(step.get("state_set"), dict):
        target_expr, raw_value = next(iter(step["state_set"].items()))
        if isinstance(raw_value, (dict, list, str)):
            roles.update(_collect_state_roles_from_runtime_value_surface(raw_value))
    return roles


def _state_target_role_from_step_item(step: JSONObject) -> str | None:
    if isinstance(step.get("state_set"), dict) and step["state_set"]:
        target_expr = next(iter(step["state_set"].keys()))
        if isinstance(target_expr, str):
            try:
                return parse_state_path(target_expr).state_role
            except StatePathParseError:
                return None
    target_expr = step.get("state_delete")
    if isinstance(target_expr, str):
        try:
            return parse_state_path(target_expr).state_role
        except StatePathParseError:
            return None
    return None


def _collect_state_roles_from_runtime_value_surface(value: JSONValue | None) -> set[str]:
    roles: set[str] = set()
    if _is_format_value_object(value):
        for arg in value.get("args", []):
            roles.update(_collect_state_roles_from_runtime_value_surface(arg))
        return roles
    if isinstance(value, list):
        for item in value:
            roles.update(_collect_state_roles_from_runtime_value_surface(item))
        return roles
    if isinstance(value, dict):
        for item in value.values():
            roles.update(_collect_state_roles_from_runtime_value_surface(item))
        return roles
    if not isinstance(value, str):
        return roles
    expression = _extract_runtime_value_expression(value)
    if expression is None:
        return roles
    try:
        parsed = parse_embedded_value_local_expression(value)
    except LOCAL_EXPRESSION_PARSE_ERRORS:
        return roles
    if parsed is None or parsed.value is None:
        return roles
    return _collect_value_state_references(parsed.value.root)


def _collect_value_state_references(node: ValueExpressionNode) -> set[str]:
    roles: set[str] = set()

    def visit(current: ValueExpressionNode) -> None:
        if isinstance(current, ValueStateReferenceNode):
            roles.add(current.state_role)
            return
        if isinstance(current, AdapterBindingNode):
            visit(current.value)
            return
        if isinstance(current, AdapterInvocationNode):
            for binding in current.bindings:
                visit(binding)
            return
        if isinstance(current, CallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, CallArgumentNode):
            visit(current.value)
            return
        if isinstance(current, ObjectEntryNode):
            visit(current.value)
            return
        if isinstance(current, ObjectNode):
            for entry in current.entries:
                visit(entry)
            return
        if isinstance(current, PipelineNode):
            visit(current.source)
            for filter_node in current.filters:
                visit(filter_node)
            return
        if isinstance(current, BuiltinCallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, ListNode):
            for item in current.items:
                visit(item)
            return
        if isinstance(current, UnaryNode):
            visit(current.operand)
            return
        if isinstance(current, BinaryNode):
            visit(current.left)
            visit(current.right)

    visit(node)
    return roles


def _collect_value_input_references(node: ValueExpressionNode) -> set[tuple[str, ...]]:
    references: set[tuple[str, ...]] = set()

    def visit(current: ValueExpressionNode) -> None:
        if isinstance(current, ReferenceNode):
            if current.parts and current.parts[0] == "inputs" and len(current.parts) >= 2:
                references.add(current.parts)
            return
        if isinstance(current, ValueStateReferenceNode):
            if current.key_reference and current.key_reference[0] == "inputs" and len(current.key_reference) >= 2:
                references.add(current.key_reference)
            return
        if isinstance(current, StepReferenceNode):
            return
        if isinstance(current, AdapterBindingNode):
            visit(current.value)
            return
        if isinstance(current, AdapterInvocationNode):
            for binding in current.bindings:
                visit(binding)
            return
        if isinstance(current, CallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, CallArgumentNode):
            visit(current.value)
            return
        if isinstance(current, PipelineNode):
            visit(current.source)
            for filter_node in current.filters:
                visit(filter_node)
            return
        if isinstance(current, BuiltinCallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, UnaryNode):
            visit(current.operand)
            return
        if isinstance(current, BinaryNode):
            visit(current.left)
            visit(current.right)
            return
        if isinstance(current, FilterApplicationNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, ListNode):
            for item in current.items:
                visit(item)
            return
        if isinstance(current, ObjectEntryNode):
            visit(current.value)
            return
        if isinstance(current, ObjectNode):
            for entry in current.entries:
                visit(entry)
            return
        if isinstance(current, LiteralNode):
            return

    visit(node)
    return references


def _validate_step_references(
    references: tuple[StepReferenceNode, ...],
    *,
    path: tuple[str, ...],
    source: str,
    prior_registers: dict[str, tuple[str, ...]],
    declared_registers: dict[str, tuple[str, ...]],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for reference in references:
        if not reference.fields or reference.fields[0] not in {"status", "summary", "outputs", "results"}:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step_ref.surface",
                    "Registered step references must use status, summary, outputs, or results as the first field",
                    path,
                    source,
                    register=reference.register,
                    fields=list(reference.fields),
                )
            )
            continue
        if reference.register in prior_registers:
            continue
        if reference.register in declared_registers:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step_ref.forward",
                    f"Registered step '{reference.register}' must be declared by an earlier step",
                    path,
                    source,
                    register=reference.register,
                    declared_at=list(declared_registers[reference.register]),
                )
            )
            continue
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step_ref.unknown",
                f"Registered step '{reference.register}' is not declared in this workflow",
                path,
                source,
                register=reference.register,
            )
        )
    return diagnostics


def _validate_state_path_text(value: JSONValue | None, *, path: tuple[str, ...], source: str) -> list[Diagnostic]:
    if not isinstance(value, str) or not value:
        return []
    try:
        parse_state_path(value)
    except StatePathParseError as exc:
        return [exc.to_diagnostic(path=path, source=source, expression=value)]
    return []


def _validate_checks(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if value is None:
        return diagnostics
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.profile.checks.type", "Field 'checks' must be a list", ("checks",), source, actual_type=type(value).__name__))
        return diagnostics

    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            diagnostics.append(_diagnostic("validation.profile.checks.item_type", "Check entries must be non-empty strings", ("checks", str(index)), source, actual_type=type(item).__name__))
    return diagnostics


def _validate_overrides(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if value is None:
        return diagnostics
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.profile.overrides.type", "Field 'overrides' must be a list", ("overrides",), source, actual_type=type(value).__name__))
        return diagnostics

    seen_targets: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(value):
        path = ("overrides", str(index))
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("validation.profile.override.type", "Override entry must be an object", path, source, actual_type=type(item).__name__))
            continue

        diagnostics.extend(_validate_unknown_fields(item, OVERRIDE_ALLOWED_FIELDS, path=path, source=source))
        diagnostics.extend(_require_non_empty_string(item, "target", path=path + ("target",), source=source, pattern=USES_PATTERN, pattern_message="Override target must match the stable operation reference pattern"))
        diagnostics.extend(_require_object_field(item, "with", path=path + ("with",), source=source, required=False))

        reason = item.get("reason")
        if reason is not None and (not isinstance(reason, str) or not reason):
            diagnostics.append(_diagnostic("validation.profile.override.reason_type", "Override reason must be a non-empty string when provided", path + ("reason",), source, actual_type=type(reason).__name__))

        target = item.get("target")
        if isinstance(target, str) and target:
            if target in seen_targets:
                diagnostics.append(_diagnostic("validation.profile.override.duplicate_target", f"Duplicate override target '{target}'", path + ("target",), source, first_seen_path=list(seen_targets[target])))
            else:
                seen_targets[target] = path + ("target",)

    return diagnostics


def _validate_launchers(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if value is None:
        return diagnostics
    if not isinstance(value, dict):
        diagnostics.append(_diagnostic("validation.profile.launchers.type", "Field 'launchers' must be an object", ("launchers",), source, actual_type=type(value).__name__))
        return diagnostics

    for name, item in value.items():
        path = ("launchers", str(name))
        if not isinstance(name, str) or not name:
            diagnostics.append(_diagnostic("validation.profile.launcher.name", "Launcher names must be non-empty strings", path, source))
        elif LAUNCHER_NAME_PATTERN.fullmatch(name) is None:
            diagnostics.append(_diagnostic("validation.profile.launcher.name_pattern", "Launcher names must match the stable launcher name pattern", path, source, pattern=LAUNCHER_NAME_PATTERN.pattern))
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("validation.profile.launcher.type", "Launcher definition must be an object", path, source, actual_type=type(item).__name__))
            continue
        diagnostics.extend(_validate_unknown_fields(item, LAUNCHER_ALLOWED_FIELDS, path=path, source=source))
        has_file = "file" in item
        has_inline_fields = any(field in item for field in ("connector", "before", "after"))
        if has_file and has_inline_fields:
            diagnostics.append(_diagnostic("validation.profile.launcher.ambiguous_source", "Launcher definition cannot mix 'file' with inline fields", path, source))
        if not has_file and not has_inline_fields:
            diagnostics.append(_diagnostic("validation.profile.launcher.empty", "Launcher definition must declare 'file' or at least one inline field", path, source))
        if "file" in item:
            diagnostics.extend(_require_non_empty_string(item, "file", path=path + ("file",), source=source))
        if "connector" in item:
            diagnostics.extend(_require_non_empty_string(item, "connector", path=path + ("connector",), source=source, pattern=USES_PATTERN, pattern_message="Launcher connector must match the stable operation reference pattern"))
        if "before" in item:
            diagnostics.extend(_require_non_empty_string(item, "before", path=path + ("before",), source=source))
        if "after" in item:
            diagnostics.extend(_require_non_empty_string(item, "after", path=path + ("after",), source=source))
    return diagnostics


def _validate_connector_context_field(value: JSONValue | None, *, path: tuple[str, ...], source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if value is None:
        return diagnostics
    if not isinstance(value, dict):
        diagnostics.append(_diagnostic("validation.connector_context.type", "Connector context must be an object", path, source, actual_type=type(value).__name__))
        return diagnostics
    for family, entry in value.items():
        family_path = path + (str(family),)
        if not isinstance(family, str) or not family:
            diagnostics.append(
                _diagnostic(
                    "validation.connector_context.family_name",
                    "Connector context keys must be non-empty strings",
                    family_path,
                    source,
                    family=family,
                )
            )
            continue
        if not isinstance(entry, dict):
            diagnostics.append(
                _diagnostic(
                    "validation.connector_context.family_type",
                    f"Connector context entry '{family}' must be an object",
                    family_path,
                    source,
                    family=family,
                    actual_type=type(entry).__name__,
                )
            )
    return diagnostics


def _validate_step_launcher(value: JSONObject, *, path: tuple[str, ...], source: str, can_use_launcher: bool) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    launcher = value.get("launcher")
    if launcher is None:
        return diagnostics
    if not can_use_launcher:
        diagnostics.append(_diagnostic("validation.workflow.step.launcher_without_uses", "Step field 'launcher' is allowed only together with 'uses'", path + ("launcher",), source))
        return diagnostics
    if not isinstance(launcher, str):
        diagnostics.append(_diagnostic("validation.workflow.step.launcher.type", "Step field 'launcher' must be a string", path + ("launcher",), source, actual_type=type(launcher).__name__))
        return diagnostics
    if not launcher:
        diagnostics.append(_diagnostic("validation.workflow.step.launcher.empty", "Step field 'launcher' must not be empty", path + ("launcher",), source))
        return diagnostics
    if LAUNCHER_NAME_PATTERN.fullmatch(launcher) is None:
        diagnostics.append(_diagnostic("validation.workflow.step.launcher.pattern", "Step field 'launcher' must match the stable launcher name pattern", path + ("launcher",), source, pattern=LAUNCHER_NAME_PATTERN.pattern))
    return diagnostics


def _validate_unknown_fields(data: JSONObject, allowed: frozenset[str], *, path: tuple[str, ...], source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for key in data:
        if key not in allowed:
            diagnostics.append(_diagnostic("validation.unknown_field", f"Unknown field '{key}'", path + (key,), source, allowed_fields=sorted(allowed)))
    return diagnostics


def _require_exact_int(data: JSONObject, key: str, expected: int, *, source: str) -> list[Diagnostic]:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return [_diagnostic(f"validation.{key}.type", f"Field '{key}' must be an integer", (key,), source, actual_type=type(value).__name__)]
    if value != expected:
        return [_diagnostic(f"validation.{key}.value", f"Field '{key}' must equal {expected}", (key,), source, actual_value=value)]
    return []


def _require_non_empty_string(
    data: JSONObject,
    key: str,
    *,
    source: str,
    path: tuple[str, ...] | None = None,
    pattern: re.Pattern[str] | None = None,
    pattern_message: str | None = None,
) -> list[Diagnostic]:
    value = data.get(key)
    result_path = path or (key,)
    if not isinstance(value, str):
        return [_diagnostic(f"validation.{key}.type", f"Field '{key}' must be a string", result_path, source, actual_type=type(value).__name__)]
    if not value:
        return [_diagnostic(f"validation.{key}.empty", f"Field '{key}' must not be empty", result_path, source)]
    if pattern is not None and pattern.fullmatch(value) is None:
        return [_diagnostic(f"validation.{key}.pattern", pattern_message or f"Field '{key}' has invalid format", result_path, source, actual_value=value)]
    return []


def _require_object_field(
    data: JSONObject,
    key: str,
    *,
    source: str,
    path: tuple[str, ...] | None = None,
    required: bool,
) -> list[Diagnostic]:
    if key not in data:
        return [] if not required else [_diagnostic(f"validation.{key}.missing", f"Field '{key}' is required", path or (key,), source)]
    value = data[key]
    if not isinstance(value, dict):
        return [_diagnostic(f"validation.{key}.type", f"Field '{key}' must be an object", path or (key,), source, actual_type=type(value).__name__)]
    return []


def _require_list_field(
    data: JSONObject,
    key: str,
    *,
    source: str,
    path: tuple[str, ...] | None = None,
    required: bool,
) -> list[Diagnostic]:
    if key not in data:
        return [] if not required else [_diagnostic(f"validation.{key}.missing", f"Field '{key}' is required", path or (key,), source)]
    value = data[key]
    if not isinstance(value, list):
        return [_diagnostic(f"validation.{key}.type", f"Field '{key}' must be a list", path or (key,), source, actual_type=type(value).__name__)]
    return []


def _diagnostic(code: str, message: str, path: tuple[str, ...], source: str, **details: object) -> Diagnostic:
    payload = {"source": source, **details}
    return Diagnostic(code=code, level="error", message=message, path=path, details=payload)


def _warning(code: str, message: str, path: tuple[str, ...], source: str, **details: object) -> Diagnostic:
    payload = {"source": source, **details}
    return Diagnostic(code=code, level="warning", message=message, path=path, details=payload)


def _report(document_kind: str, diagnostics: list[Diagnostic]) -> ValidationReport:
    deduplicated = _deduplicate_diagnostics(diagnostics)
    if any(diagnostic.level == "error" for diagnostic in deduplicated):
        return ValidationReport(document_kind=document_kind, status=RuntimeStatus.VALIDATION_ERROR, diagnostics=tuple(deduplicated))
    return ValidationReport(document_kind=document_kind, status=RuntimeStatus.OK, diagnostics=tuple(deduplicated))


def _deduplicate_diagnostics(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    seen: set[tuple[str, str, str, tuple[str, ...], str]] = set()
    deduplicated: list[Diagnostic] = []
    for diagnostic in diagnostics:
        key = (
            diagnostic.code,
            diagnostic.level,
            diagnostic.message,
            diagnostic.path,
            json.dumps(diagnostic.details, sort_keys=True, default=str),
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(diagnostic)
    return deduplicated
