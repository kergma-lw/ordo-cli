"""Recommendation logic for no-argument playbook-level next mode."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ordo.model.diagnostic import Diagnostic
from ordo.model.workflow import GuardBlock, RunBlock, Step, StepBlock, Workflow
from ordo.model.runtime import RuntimeResult, RuntimeStatus
from ordo.runtime.conditions import iter_condition_expression_leaves, normalize_condition_authoring
from ordo.runtime.local_expression_contexts import LocalExpressionContext
from ordo.runtime.local_expressions import parse_condition_local_expression, parse_value_local_expression
from ordo.runtime.local_expression_engine.core import (
    BinaryNode,
    BuiltinCallNode,
    CallArgumentNode,
    CallNode,
    FilterApplicationNode,
    ListNode,
    ObjectEntryNode,
    ObjectNode,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode,
    StepReferenceNode,
    UnaryNode,
    ValueExpressionNode,
    collect_local_expression_dependencies,
    render_expression_text,
)
from ordo.runtime.state import RuntimeStateError, read_state_document, read_state_value, resolve_state_target
from ordo.runtime.state_paths import ParsedStatePath, parse_state_path
from ordo.runtime.resolution import ResolvedBuiltinStep, ResolvedOperation, ResolvedRunStep, ResolvedStepBlock, resolve_workflow_references


@dataclass(frozen=True, slots=True)
class StatePathReference:
    expression: str
    state_role: str
    binding_name: str | None
    key_expression: str
    fields: tuple[str, ...] = ()
    source_kind: str = "read"
    surface_kind: str = "unknown"

    @property
    def logical_signature(self) -> str:
        root = self.binding_name or self.state_role
        suffix = ".".join(self.fields)
        return root if not suffix else f"{root}.{suffix}"


@dataclass(frozen=True, slots=True)
class WorkflowTopology:
    reads: tuple[StatePathReference, ...] = ()
    writes: tuple[StatePathReference, ...] = ()
    deletes: tuple[StatePathReference, ...] = ()
    role: str = "utility"
    contextual_inputs: tuple[str, ...] = ()
    execution_only_inputs: tuple[str, ...] = ()
    effectful_step_count: int = 0


@dataclass(frozen=True, slots=True)
class NextCandidate:
    """Rankable next-workflow candidate built from activation and runtime evidence."""

    workflow: str
    description: str | None = None
    workflow_category: str | None = None
    when: str | None = None
    working_directory: str | None = None
    candidate_class: str = "weak_match"
    score: int = 0
    allowed: bool = False
    reason_category: str | None = None
    matched_guard_count: int = 0
    relevant_guard_count: int = 0
    evaluated_guard_count: int = 0
    full_evaluability: bool = False
    blockers: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    missing_input_kind: str | None = None
    input_blocker_count: int = 0
    world_blocker_count: int = 0
    ranking_factors: tuple[dict[str, object], ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    state_role: str = "utility"
    state_affinity_score: int = 0
    state_cluster: tuple[str, ...] = ()
    active_state_paths: tuple[str, ...] = ()
    caller_inputs: tuple[str, ...] = ()
    optional_caller_inputs: tuple[str, ...] = ()
    topology: WorkflowTopology | None = None
    effectful_step_count: int = 0

    def to_contract(self) -> dict[str, object]:
        return {
            "workflow": self.workflow,
            "description": self.description,
            "category": self.workflow_category,
            "when": self.when,
            "working_directory": self.working_directory,
            "candidate_class": self.candidate_class,
            "score": self.score,
            "allowed": self.allowed,
            "reason_category": self.reason_category,
            "matched_guard_count": self.matched_guard_count,
            "relevant_guard_count": self.relevant_guard_count,
            "evaluated_guard_count": self.evaluated_guard_count,
            "full_evaluability": self.full_evaluability,
            "blockers": list(self.blockers),
            "missing_inputs": list(self.missing_inputs),
            "missing_input_kind": self.missing_input_kind,
            "input_blocker_count": self.input_blocker_count,
            "world_blocker_count": self.world_blocker_count,
            "ranking_factors": [dict(item) for item in self.ranking_factors],
            "diagnostics": [diagnostic.to_contract() for diagnostic in self.diagnostics],
            "state_role": self.state_role,
            "state_affinity_score": self.state_affinity_score,
            "state_cluster": list(self.state_cluster),
            "active_state_paths": list(self.active_state_paths),
            "caller_inputs": list(self.caller_inputs),
            "optional_caller_inputs": list(self.optional_caller_inputs),
            "effectful_step_count": self.effectful_step_count,
        }


@dataclass(frozen=True, slots=True)
class _BuiltCandidate:
    candidate: NextCandidate
    concrete_active_reads: tuple[str, ...] = ()


def build_next_candidate(
    *,
    workflow: str,
    description: str | None,
    workflow_category: str | None,
    when: str | None,
    working_directory: str | None,
    runtime_result: RuntimeResult | None = None,
    diagnostics: tuple[Diagnostic, ...] = (),
    workflow_contract: Workflow | None = None,
    runtime_workflow: Workflow | None = None,
    caller_inputs: tuple[str, ...] = (),
    optional_caller_inputs: tuple[str, ...] = (),
) -> NextCandidate:
    """Build one candidate from either runtime evaluation or activation diagnostics."""

    topology = analyze_workflow_topology(runtime_workflow or workflow_contract)
    if runtime_result is None:
        candidate = _candidate_from_diagnostics(
            workflow=workflow,
            description=description,
            workflow_category=workflow_category,
            when=when,
            working_directory=working_directory,
            diagnostics=diagnostics,
            topology=topology,
            workflow_contract=workflow_contract,
            caller_inputs=caller_inputs,
            optional_caller_inputs=optional_caller_inputs,
        )
    else:
        candidate = _candidate_from_runtime_result(
            workflow=workflow,
            description=description,
            workflow_category=workflow_category,
            when=when,
            working_directory=working_directory,
            result=runtime_result,
            topology=topology,
            workflow_contract=workflow_contract if workflow_contract is not None else runtime_workflow,
            caller_inputs=caller_inputs,
            optional_caller_inputs=optional_caller_inputs,
        )
    concrete_active_reads = _resolve_existing_state_reads(runtime_workflow, topology)
    built = _BuiltCandidate(candidate=candidate, concrete_active_reads=concrete_active_reads)
    return replace(built.candidate, active_state_paths=built.concrete_active_reads)


def rank_next_candidates(
    candidates: list[NextCandidate],
    *,
    requested_profile: str | None,
    input_override_keys: list[str],
    playbook_path: str,
    include_graph: bool = False,
) -> dict[str, object]:
    """Build the public next-mode payload from ranked candidates."""

    active_state_paths = _global_active_state_paths(candidates)
    active_cluster = _global_active_state_cluster(candidates, active_state_paths=active_state_paths)
    enriched = _enrich_with_state_affinity(candidates, active_state_paths=active_state_paths, active_cluster=active_cluster)
    ordered = sorted(
        enriched,
        key=lambda item: (
            _semantic_precedence(item, active_state_paths=active_state_paths),
            -item.score,
            _class_order(item.candidate_class),
            item.workflow,
        ),
    )
    best = ordered[0] if ordered else None
    alternatives = ordered[1:4] if len(ordered) > 1 else []
    strength = "none"
    uncertainty: dict[str, object] | None = None
    if best is not None:
        strength = _recommendation_strength(best, alternatives)
        if best.candidate_class not in {"ready_now", "context_inspector", "inspection_only", "ready_with_execution_input"}:
            uncertainty = {
                "kind": "no_ready_now_candidate",
                "message": "No workflow is runnable now; returning the strongest near-term candidate from current evidence.",
            }
        elif alternatives and abs(best.score - alternatives[0].score) < 40:
            uncertainty = {
                "kind": "competitive_candidates",
                "message": "Multiple workflows are materially close; review nearby alternatives before choosing automatically.",
            }
    else:
        uncertainty = {
            "kind": "no_candidates",
            "message": "No visible workflow candidate could be analyzed from the current playbook context.",
        }

    payload = {
        "mode": "next",
        "status": "ok",
        "playbook": playbook_path,
        "profile": requested_profile,
        "scope": "playbook",
        "current_context": {
            "requested_profile": requested_profile,
            "input_override_keys": list(input_override_keys),
            "active_state_paths": list(active_state_paths),
            "active_state_cluster": list(active_cluster),
        },
        "ready_now_available": best is not None and best.candidate_class in {"ready_now", "context_inspector", "inspection_only", "ready_with_execution_input"},
        "recommendation_strength": strength,
        "best_candidate": None if best is None else best.to_contract(),
        "alternatives": [item.to_contract() for item in alternatives],
        "candidates": [item.to_contract() for item in ordered],
        "uncertainty": uncertainty,
    }
    if include_graph:
        payload["graph"] = build_next_graph_payload(
            ordered,
            active_state_paths=active_state_paths,
            active_cluster=active_cluster,
        )
    return payload


def build_next_graph_payload(
    candidates: list[NextCandidate],
    *,
    active_state_paths: tuple[str, ...],
    active_cluster: tuple[str, ...],
) -> dict[str, object]:
    return {
        "active_state_paths": list(active_state_paths),
        "active_state_cluster": list(active_cluster),
        "workflows": [_candidate_graph_node(candidate) for candidate in candidates],
    }


def _candidate_graph_node(candidate: NextCandidate) -> dict[str, object]:
    topology = candidate.topology
    reads = [] if topology is None else [_state_reference_contract(item) for item in topology.reads]
    writes = [] if topology is None else [_state_reference_contract(item) for item in topology.writes]
    deletes = [] if topology is None else [_state_reference_contract(item) for item in topology.deletes]
    return {
        "workflow": candidate.workflow,
        "score": candidate.score,
        "score_breakdown": _graph_score_breakdown(candidate),
        "candidate_class": candidate.candidate_class,
        "state_role": candidate.state_role,
        "active_state_paths": list(candidate.active_state_paths),
        "state_cluster": list(candidate.state_cluster),
        "reads": reads,
        "writes": writes,
        "deletes": deletes,
        "missing_inputs": list(candidate.missing_inputs),
        "missing_input_kind": candidate.missing_input_kind,
        "input_blocker_count": candidate.input_blocker_count,
        "world_blocker_count": candidate.world_blocker_count,
        "effectful_step_count": candidate.effectful_step_count,
    }


def _graph_score_breakdown(candidate: NextCandidate) -> dict[str, object]:
    guard_factors: list[dict[str, object]] = []
    state_factors: list[dict[str, object]] = []
    guard_total = 0
    state_total = 0
    for item in candidate.ranking_factors:
        factor = item.get("factor")
        value = item.get("value")
        effect = item.get("effect")
        if not isinstance(factor, str) or not isinstance(value, int) or effect not in {"bonus", "penalty"}:
            continue
        signed_value = value if effect == "bonus" else -value
        target = state_factors if factor in {"state_affinity", "execution_only_input", "execution_only_preference", "inspect_penalty", "inspection_only_penalty", "effectful_continuation", "world_blocker_penalty", "unrelated_utility_penalty"} else guard_factors
        target.append(
            {
                "factor": factor,
                "signed_value": signed_value,
                "why": item.get("why"),
            }
        )
        if target is guard_factors:
            guard_total += signed_value
        else:
            state_total += signed_value
    return {
        "guard_score": guard_total,
        "state_score": state_total,
        "guard_factors": guard_factors,
        "state_factors": state_factors,
    }


def _state_reference_contract(reference: StatePathReference) -> dict[str, object]:
    return {
        "expression": reference.expression,
        "logical_signature": reference.logical_signature,
        "key_expression": reference.key_expression,
        "fields": list(reference.fields),
        "source_kind": reference.source_kind,
        "surface_kind": reference.surface_kind,
    }


def analyze_workflow_topology(workflow: Workflow | None) -> WorkflowTopology | None:
    if workflow is None or not hasattr(workflow, "blocks") or not hasattr(workflow, "let_bindings") or not hasattr(workflow, "state_bindings"):
        return None
    reads: list[StatePathReference] = []
    writes: list[StatePathReference] = []
    deletes: list[StatePathReference] = []
    contextual_inputs: set[str] = set()
    execution_only_inputs: set[str] = set()
    effectful_counter = [0]

    def remember_surface(kind: str, expression: str, *, context: LocalExpressionContext, force_contextual_inputs: bool = False) -> None:
        try:
            parsed = (
                parse_condition_local_expression(expression, context=context)
                if context in {LocalExpressionContext.GUARD, LocalExpressionContext.STEP_CONDITION}
                else parse_value_local_expression(expression, context=context, allow_boolean_composition=True)
            )
        except Exception:
            return
        read_refs = _collect_state_refs_from_node(parsed.root, source=parsed.source, workflow=workflow, surface_kind=kind)
        reads.extend(ref for ref in read_refs if ref.logical_signature not in {item.logical_signature for item in reads})
        input_names = _collect_input_names_from_node(parsed.root)
        dependency_roots = {item.name for item in collect_local_expression_dependencies(parsed.root) if item.kind in {"root", "observation"}}
        for input_name in input_names:
            if force_contextual_inputs or (dependency_roots - {"inputs"}):
                contextual_inputs.add(input_name)
                execution_only_inputs.discard(input_name)
            elif input_name not in contextual_inputs:
                execution_only_inputs.add(input_name)

    for expression in workflow.let_bindings.values():
        if isinstance(expression, str):
            remember_surface("let", expression, context=LocalExpressionContext.EMBEDDED_VALUE)

    for block in workflow.blocks:
        if isinstance(block, GuardBlock):
            for guard in block.guards:
                if isinstance(guard.expr, str):
                    remember_surface("guard", guard.expr, context=LocalExpressionContext.GUARD)
            continue
        if isinstance(block, RunBlock):
            if block.if_ is not None:
                for _, expression in _condition_leaves(block.if_):
                    remember_surface("run.if", expression, context=LocalExpressionContext.STEP_CONDITION)
            _remember_value_surfaces(block.with_, kind="run.with", remember_surface=remember_surface)
            continue
        if isinstance(block, StepBlock):
            for step in block.steps:
                _collect_step_topology(
                    workflow,
                    step,
                    reads=reads,
                    writes=writes,
                    deletes=deletes,
                    remember_surface=remember_surface,
                    effectful_counter=effectful_counter,
                )

    role = _infer_state_role(workflow, reads=reads, writes=writes, deletes=deletes)
    return WorkflowTopology(
        reads=tuple(reads),
        writes=tuple(writes),
        deletes=tuple(deletes),
        role=role,
        contextual_inputs=tuple(sorted(contextual_inputs)),
        execution_only_inputs=tuple(sorted(item for item in execution_only_inputs if item not in contextual_inputs)),
        effectful_step_count=effectful_counter[0],
    )


def classify_missing_input_kind_for_workflow(workflow: Workflow | None, missing_inputs: tuple[str, ...]) -> str | None:
    topology = analyze_workflow_topology(workflow)
    return _classify_missing_input_kind(missing_inputs, topology=topology)


def _collect_step_topology(
    workflow: Workflow,
    step: Step,
    *,
    reads: list[StatePathReference],
    writes: list[StatePathReference],
    deletes: list[StatePathReference],
    remember_surface,
    effectful_counter,
) -> None:
    if _step_is_effectfulish(step):
        effectful_counter[0] += 1
    if step.if_ is not None:
        for _, expression in _condition_leaves(step.if_):
            remember_surface("step.if", expression, context=LocalExpressionContext.STEP_CONDITION)
    if step.gate is not None:
        for _, expression in _condition_leaves(step.gate):
            remember_surface("step.gate", expression, context=LocalExpressionContext.STEP_CONDITION)
    if step.for_each is not None:
        _remember_value_surfaces(step.for_each, kind="step.for_each", remember_surface=remember_surface)
    if step.operation is not None:
        _remember_value_surfaces(step.operation.with_, kind="step.operation.with", remember_surface=remember_surface)
    if step.run is not None:
        _remember_value_surfaces(step.run_with, kind="step.run.with", remember_surface=remember_surface)
        _remember_value_surfaces(step.run_state_bindings, kind="step.run.state_bindings", remember_surface=remember_surface)
        _remember_value_surfaces(step.run_states, kind="step.run.states", remember_surface=remember_surface)
    if step.steps is not None:
        for inner in step.steps:
            _collect_step_topology(workflow, inner, reads=reads, writes=writes, deletes=deletes, remember_surface=remember_surface, effectful_counter=effectful_counter)
    if step.profile_switch is not None:
        _remember_value_surfaces(step.profile_switch, kind="step.profile_switch", remember_surface=lambda kind, expression, context, force_contextual_inputs=False: remember_surface(kind, expression, context=context, force_contextual_inputs=True))
    if step.value is not None:
        _remember_value_surfaces(step.value, kind="step.value", remember_surface=remember_surface)
    if step.result is not None:
        _remember_value_surfaces(step.result, kind="step.result", remember_surface=remember_surface)
    if step.publish is not None:
        _remember_value_surfaces(step.publish, kind="step.publish", remember_surface=remember_surface)
    if step.state_set is not None:
        for raw_path, raw_value in step.state_set.items():
            reference = _state_ref_from_path(raw_path, workflow=workflow, source_kind="write", surface_kind="step.state_set")
            if reference is not None and reference.logical_signature not in {item.logical_signature for item in writes}:
                writes.append(reference)
            if isinstance(reference, StatePathReference):
                remember_surface(
                    "step.state_set.key",
                    reference.key_expression,
                    context=LocalExpressionContext.EMBEDDED_VALUE,
                    force_contextual_inputs=True,
                )
            _remember_value_surfaces(raw_value, kind="step.state_set.value", remember_surface=lambda kind, expression, context, force_contextual_inputs=False: remember_surface(kind, expression, context=context, force_contextual_inputs=True))
    if step.state_delete is not None:
        reference = _state_ref_from_path(step.state_delete, workflow=workflow, source_kind="delete", surface_kind="step.state_delete")
        if reference is not None and reference.logical_signature not in {item.logical_signature for item in deletes}:
            deletes.append(reference)
        if isinstance(reference, StatePathReference):
            remember_surface(
                "step.state_delete.key",
                reference.key_expression,
                context=LocalExpressionContext.EMBEDDED_VALUE,
                force_contextual_inputs=True,
            )


def _remember_value_surfaces(value: object, *, kind: str, remember_surface) -> None:
    if isinstance(value, str):
        remember_surface(kind, value, context=LocalExpressionContext.EMBEDDED_VALUE)
        return
    if isinstance(value, list):
        for item in value:
            _remember_value_surfaces(item, kind=kind, remember_surface=remember_surface)
        return
    if isinstance(value, dict):
        for item in value.values():
            _remember_value_surfaces(item, kind=kind, remember_surface=remember_surface)
def _step_is_effectfulish(step: Step) -> bool:
    return step.operation is not None or step.run is not None or step.steps is not None or step.state_set is not None or step.state_delete is not None


def _condition_leaves(value: object) -> list[tuple[tuple[str, ...], str]]:
    if not isinstance(value, (str, list, dict)):
        return []
    try:
        normalized = normalize_condition_authoring(value)
    except Exception:
        return []
    return iter_condition_expression_leaves(normalized)


def _collect_state_refs_from_node(
    node: ValueExpressionNode,
    *,
    source: str,
    workflow: Workflow,
    surface_kind: str,
) -> tuple[StatePathReference, ...]:
    found: list[StatePathReference] = []

    def visit(current: ValueExpressionNode) -> None:
        if isinstance(current, StateReferenceNode):
            expression = render_expression_text(current, source=source)
            key_expression = render_expression_text(current.key_expression, source=source)
            found.append(
                StatePathReference(
                    expression=expression,
                    state_role=current.state_role,
                    binding_name=workflow.state_bindings.get(current.state_role) if isinstance(workflow.state_bindings, dict) else None,
                    key_expression=key_expression,
                    fields=current.fields,
                    source_kind="read",
                    surface_kind=surface_kind,
                )
            )
            visit(current.key_expression)
            return
        if isinstance(current, StepReferenceNode):
            return
        if isinstance(current, ReferenceNode):
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
        if isinstance(current, CallArgumentNode):
            visit(current.value)
            return
        if isinstance(current, CallNode):
            for argument in current.arguments:
                visit(argument)
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
            return

    visit(node)
    unique: list[StatePathReference] = []
    seen: set[tuple[str, str, tuple[str, ...], str]] = set()
    for item in found:
        marker = (item.state_role, item.key_expression, item.fields, item.surface_kind)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(item)
    return tuple(unique)


def _collect_input_names_from_node(node: ValueExpressionNode) -> tuple[str, ...]:
    names: list[str] = []

    def remember(name: str) -> None:
        if name not in names:
            names.append(name)

    def visit(current: ValueExpressionNode) -> None:
        if isinstance(current, ReferenceNode):
            if current.parts and current.parts[0] == "inputs" and len(current.parts) >= 2:
                remember(current.parts[1])
            return
        if isinstance(current, StateReferenceNode):
            visit(current.key_expression)
            return
        if isinstance(current, StepReferenceNode):
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
        if isinstance(current, CallArgumentNode):
            visit(current.value)
            return
        if isinstance(current, CallNode):
            for argument in current.arguments:
                visit(argument)
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
            return

    visit(node)
    return tuple(names)


def _state_ref_from_path(
    expression: str,
    *,
    workflow: Workflow,
    source_kind: str,
    surface_kind: str,
) -> StatePathReference | None:
    if not isinstance(expression, str):
        return None
    try:
        parsed: ParsedStatePath = parse_state_path(expression)
    except Exception:
        return None
    return StatePathReference(
        expression=expression,
        state_role=parsed.state_role,
        binding_name=workflow.state_bindings.get(parsed.state_role) if isinstance(workflow.state_bindings, dict) else None,
        key_expression=parsed.key_expression,
        fields=parsed.fields,
        source_kind=source_kind,
        surface_kind=surface_kind,
    )


def _infer_state_role(
    workflow: Workflow,
    *,
    reads: list[StatePathReference],
    writes: list[StatePathReference],
    deletes: list[StatePathReference],
) -> str:
    if deletes:
        return "close"
    if writes and reads:
        return "transition"
    if writes and not reads:
        return "producer"
    if reads:
        return "inspect"
    return "utility"


def _resolve_existing_state_reads(workflow: Workflow | None, topology: WorkflowTopology | None) -> tuple[str, ...]:
    if workflow is None or topology is None or not hasattr(workflow, "state_bindings"):
        return ()
    found: list[str] = []
    for reference in topology.reads:
        try:
            target = resolve_state_target(reference.expression, workflow)
            document = read_state_document(target.location)
            value = read_state_value(document, key=target.key, fields=target.fields)
        except RuntimeStateError:
            continue
        if value is None:
            continue
        marker = _concrete_state_target(reference, workflow=workflow)
        if marker is not None and marker not in found:
            found.append(marker)
    return tuple(found)


def _concrete_state_target(reference: StatePathReference, *, workflow: Workflow) -> str | None:
    try:
        target = resolve_state_target(reference.expression, workflow)
    except RuntimeStateError:
        return None
    suffix = ".".join(target.fields)
    return f"{target.location.name}[{target.key}]" if not suffix else f"{target.location.name}[{target.key}].{suffix}"


def _global_active_state_paths(candidates: list[NextCandidate]) -> tuple[str, ...]:
    ordered: list[str] = []
    for candidate in candidates:
        topology = candidate.topology
        if topology is None:
            continue
        active_paths = getattr(candidate, "active_state_paths", ())
        for path in active_paths:
            if path not in ordered:
                ordered.append(path)
    return tuple(ordered)


def _global_active_state_cluster(candidates: list[NextCandidate], *, active_state_paths: tuple[str, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    logical_from_active = {path.split("[", 1)[0] for path in active_state_paths}
    for candidate in candidates:
        topology = candidate.topology
        if topology is None:
            continue
        candidate_is_active_bridge = bool(candidate.active_state_paths)
        for reference in (*topology.reads, *topology.writes, *topology.deletes):
            if reference.logical_signature in ordered:
                continue
            root = reference.logical_signature.split(".", 1)[0]
            if candidate_is_active_bridge or root in logical_from_active or reference.binding_name in logical_from_active:
                ordered.append(reference.logical_signature)
    return tuple(ordered)


def _enrich_with_state_affinity(
    candidates: list[NextCandidate],
    *,
    active_state_paths: tuple[str, ...],
    active_cluster: tuple[str, ...],
) -> list[NextCandidate]:
    active_roots = {item.split("[", 1)[0] for item in active_state_paths}
    cluster_set = set(active_cluster)
    state_connected_effectful_candidates_exist = any(
        candidate.topology is not None
        and candidate.effectful_step_count > 0
        and any(
            reference.logical_signature in cluster_set or (reference.binding_name and reference.binding_name in active_roots)
            for reference in (*candidate.topology.reads, *candidate.topology.writes, *candidate.topology.deletes)
        )
        for candidate in candidates
    )
    state_connected_execution_only_candidates_exist = any(
        candidate.topology is not None
        and candidate.effectful_step_count > 0
        and candidate.candidate_class in {"ready_with_execution_input", "awaiting_input", "awaiting_context_input"}
        and candidate.missing_input_kind == "execution_only"
        and any(
            reference.logical_signature in cluster_set or (reference.binding_name and reference.binding_name in active_roots)
            for reference in (*candidate.topology.reads, *candidate.topology.writes, *candidate.topology.deletes)
        )
        for candidate in candidates
    )
    state_connected_candidates_exist = any(
        candidate.topology is not None
        and any(
            reference.logical_signature in cluster_set or (reference.binding_name and reference.binding_name in active_roots)
            for reference in (*candidate.topology.reads, *candidate.topology.writes, *candidate.topology.deletes)
        )
        for candidate in candidates
    )
    enriched: list[NextCandidate] = []
    for candidate in candidates:
        topology = candidate.topology
        if topology is None:
            enriched.append(candidate)
            continue
        matched_logical: list[str] = []
        for reference in (*topology.reads, *topology.writes, *topology.deletes):
            if reference.logical_signature in cluster_set or (reference.binding_name and reference.binding_name in active_roots):
                if reference.logical_signature not in matched_logical:
                    matched_logical.append(reference.logical_signature)
        state_affinity_score = 0
        factors = [dict(item) for item in candidate.ranking_factors]
        if matched_logical:
            read_matches = len([item for item in topology.reads if item.logical_signature in matched_logical])
            write_or_delete_matches = len(
                [item for item in (*topology.writes, *topology.deletes) if item.logical_signature in matched_logical]
            )
            state_affinity_score += read_matches * 80
            state_affinity_score += write_or_delete_matches * 60
            state_affinity_score += 40
            factors.append(
                {
                    "factor": "state_affinity",
                    "effect": "bonus",
                    "value": state_affinity_score,
                    "why": f"workflow belongs to the active state-backed context via {', '.join(matched_logical[:3])}",
                }
            )
            if candidate.effectful_step_count > 0:
                effectful_bonus = 150 + min(max(candidate.effectful_step_count - 1, 0), 2) * 40
                state_affinity_score += effectful_bonus
                factors.append(
                    {
                        "factor": "effectful_continuation",
                        "effect": "bonus",
                        "value": effectful_bonus,
                        "why": "workflow has effectful steps inside the active state-backed context, so it can advance work rather than only inspect it",
                    }
                )
        candidate_class = candidate.candidate_class
        has_common_state_match = any(item.startswith("common_state.") for item in matched_logical)
        if (
            candidate_class == "awaiting_input"
            and candidate.missing_input_kind == "execution_only"
            and matched_logical
            and topology.role in {"inspect", "transition", "close"}
            and (has_common_state_match or candidate.caller_inputs)
        ):
            candidate_class = "ready_with_execution_input"
            factors.append(
                {
                    "factor": "execution_only_input",
                    "effect": "bonus",
                    "value": 0,
                    "why": "only execution-only input is missing; the state-backed context already identifies the work item",
                }
            )
        elif candidate_class == "awaiting_input" and matched_logical:
            candidate_class = "awaiting_context_input"
        elif candidate_class == "near_ready" and matched_logical:
            candidate_class = "near_ready_contextual"
        elif candidate_class == "ready_now" and topology.role == "inspect" and candidate.effectful_step_count == 0 and matched_logical:
            candidate_class = "inspection_only"
        class_adjustment = _candidate_class_adjustment(candidate_class) - _candidate_class_adjustment(candidate.candidate_class)
        score = candidate.score + state_affinity_score + class_adjustment
        if (
            topology.role == "inspect"
            and candidate.effectful_step_count == 0
            and matched_logical
            and state_connected_effectful_candidates_exist
            and candidate_class in {"ready_now", "inspection_only"}
        ):
            penalty = 520 if state_connected_execution_only_candidates_exist else 180
            score -= penalty
            factors.append(
                {
                    "factor": "inspection_only_penalty",
                    "effect": "penalty",
                    "value": penalty,
                    "why": "inspection-only workflow was deprioritized because state-connected continuation candidates are also available",
                }
            )
        if candidate_class == "ready_with_execution_input":
            score += 120
            factors.append(
                {
                    "factor": "execution_only_preference",
                    "effect": "bonus",
                    "value": 120,
                    "why": "workflow is already identified by active context and only needs execution-only operator input",
                }
            )
        if (
            candidate_class == "near_ready_contextual"
            and matched_logical
            and candidate.blockers
            and state_connected_execution_only_candidates_exist
        ):
            score -= 220
            factors.append(
                {
                    "factor": "world_blocker_penalty",
                    "effect": "penalty",
                    "value": 220,
                    "why": "workflow still depends on world-state blockers while another state-connected candidate only needs execution-only input",
                }
            )
        if (
            active_state_paths
            and state_connected_candidates_exist
            and not matched_logical
            and candidate_class == "ready_now"
            and topology.role == "utility"
        ):
            score -= 420
            factors.append(
                {
                    "factor": "unrelated_utility_penalty",
                    "effect": "penalty",
                    "value": 420,
                    "why": "unrelated ready-now utility workflow was deprioritized because active state already points to a more specific work context",
                }
            )
        enriched.append(
            replace(
                candidate,
                candidate_class=candidate_class,
                score=score,
                ranking_factors=tuple(factors),
                state_role=topology.role,
                state_affinity_score=state_affinity_score,
                state_cluster=tuple(matched_logical),
            )
        )
    return enriched


def _candidate_from_runtime_result(
    *,
    workflow: str,
    description: str | None,
    workflow_category: str | None,
    when: str | None,
    working_directory: str | None,
    result: RuntimeResult,
    topology: WorkflowTopology | None,
    workflow_contract: Workflow | None,
    caller_inputs: tuple[str, ...],
    optional_caller_inputs: tuple[str, ...],
) -> NextCandidate:
    explanation = result.outputs.get("explanation") if isinstance(result.outputs.get("explanation"), dict) else {}
    allowed = bool(explanation.get("allowed", result.outputs.get("can_execute", False)))
    reason_category = explanation.get("category") if isinstance(explanation.get("category"), str) else None
    blockers = tuple(item for item in explanation.get("blockers", []) if isinstance(item, str))
    matched_guard_count, relevant_guard_count, evaluated_guard_count = _guard_counts(result)
    missing_inputs = _missing_inputs_from_diagnostics(result.diagnostics)
    missing_input_kind = _classify_missing_input_kind(missing_inputs, topology=topology)
    input_blocker_count, world_blocker_count = _split_blockers(blockers, missing_inputs=missing_inputs)
    input_blocker_kind = _classify_input_blocker_kind(blockers, topology=topology)
    analysis_complete = bool(result.outputs.get("analysis_complete", True))
    full_evaluability = analysis_complete and evaluated_guard_count >= relevant_guard_count and not missing_inputs
    effectful_step_count = _static_effectful_step_count(
        topology=topology,
        workflow_contract=workflow_contract,
    )
    candidate_class = _classify_runtime_candidate(
        result=result,
        allowed=allowed,
        reason_category=reason_category,
        blockers=blockers,
        matched_guard_count=matched_guard_count,
        relevant_guard_count=relevant_guard_count,
        missing_inputs=missing_inputs,
        input_blocker_count=input_blocker_count,
        world_blocker_count=world_blocker_count,
        input_blocker_kind=input_blocker_kind,
    )
    score, ranking_factors = _score_candidate(
        candidate_class=candidate_class,
        matched_guard_count=matched_guard_count,
        relevant_guard_count=relevant_guard_count,
        full_evaluability=full_evaluability,
        blockers=blockers,
        missing_inputs=missing_inputs,
        missing_input_kind=missing_input_kind,
        input_blocker_count=input_blocker_count,
        world_blocker_count=world_blocker_count,
        input_blocker_kind=input_blocker_kind,
        reason_category=reason_category,
    )
    return NextCandidate(
        workflow=workflow,
        description=description,
        workflow_category=workflow_category,
        when=when,
        working_directory=working_directory,
        candidate_class=candidate_class,
        score=score,
        allowed=allowed,
        reason_category=reason_category,
        matched_guard_count=matched_guard_count,
        relevant_guard_count=relevant_guard_count,
        evaluated_guard_count=evaluated_guard_count,
        full_evaluability=full_evaluability,
        blockers=blockers,
        missing_inputs=missing_inputs,
        missing_input_kind=missing_input_kind,
        input_blocker_count=input_blocker_count,
        world_blocker_count=world_blocker_count,
        ranking_factors=tuple(ranking_factors),
        diagnostics=result.diagnostics,
        state_role="utility" if topology is None else topology.role,
        caller_inputs=caller_inputs,
        optional_caller_inputs=optional_caller_inputs,
        topology=topology,
        effectful_step_count=effectful_step_count,
    )


def _candidate_from_diagnostics(
    *,
    workflow: str,
    description: str | None,
    workflow_category: str | None,
    when: str | None,
    working_directory: str | None,
    diagnostics: tuple[Diagnostic, ...],
    topology: WorkflowTopology | None,
    workflow_contract: Workflow | None,
    caller_inputs: tuple[str, ...],
    optional_caller_inputs: tuple[str, ...],
) -> NextCandidate:
    missing_inputs = _missing_inputs_from_diagnostics(diagnostics)
    missing_input_kind = _classify_missing_input_kind(missing_inputs, topology=topology)
    blockers = tuple(diagnostic.code for diagnostic in diagnostics)
    input_blocker_count, world_blocker_count = _split_blockers(blockers, missing_inputs=missing_inputs)
    if missing_inputs:
        candidate_class = "awaiting_input"
        reason_category = "missing_input"
    else:
        candidate_class = "not_evaluable_now"
        reason_category = _diagnostic_reason_category(diagnostics)
    score, ranking_factors = _score_candidate(
        candidate_class=candidate_class,
        matched_guard_count=0,
        relevant_guard_count=0,
        full_evaluability=False,
        blockers=blockers,
        missing_inputs=missing_inputs,
        missing_input_kind=missing_input_kind,
        input_blocker_count=input_blocker_count,
        world_blocker_count=world_blocker_count,
        input_blocker_kind=None,
        reason_category=reason_category,
    )
    return NextCandidate(
        workflow=workflow,
        description=description,
        workflow_category=workflow_category,
        when=when,
        working_directory=working_directory,
        candidate_class=candidate_class,
        score=score,
        allowed=False,
        reason_category=reason_category,
        matched_guard_count=0,
        relevant_guard_count=0,
        evaluated_guard_count=0,
        full_evaluability=False,
        blockers=blockers,
        missing_inputs=missing_inputs,
        missing_input_kind=missing_input_kind,
        input_blocker_count=input_blocker_count,
        world_blocker_count=world_blocker_count,
        ranking_factors=tuple(ranking_factors),
        diagnostics=diagnostics,
        state_role="utility" if topology is None else topology.role,
        caller_inputs=caller_inputs,
        optional_caller_inputs=optional_caller_inputs,
        topology=topology,
        effectful_step_count=_static_effectful_step_count(topology=topology, workflow_contract=workflow_contract),
    )


def _static_effectful_step_count(*, topology: WorkflowTopology | None, workflow_contract: Workflow | None) -> int:
    if workflow_contract is None or not hasattr(workflow_contract, "blocks"):
        return 0 if topology is None else topology.effectful_step_count
    resolution = resolve_workflow_references(workflow_contract)
    if not resolution.blocks:
        return 0 if topology is None else topology.effectful_step_count
    return sum(_count_effectful_resolved_steps(block.steps) for block in resolution.blocks if isinstance(block, ResolvedStepBlock))




def _count_effectful_resolved_steps(steps: tuple[object, ...]) -> int:
    count = 0
    for step in steps:
        if isinstance(step, ResolvedOperation):
            if step.operation.kind != "probe":
                count += 1
            continue
        if isinstance(step, ResolvedBuiltinStep):
            if step.builtin in {"state_set", "state_delete"}:
                count += 1
            continue
        if isinstance(step, ResolvedRunStep):
            count += _count_effectful_resolved_steps(step.steps)
            if step.run is not None and not step.steps:
                count += 1
    return count


def _classify_missing_input_kind(missing_inputs: tuple[str, ...], *, topology: WorkflowTopology | None) -> str | None:
    if not missing_inputs:
        return None
    if topology is None:
        return "unknown"
    contextual = set(topology.contextual_inputs)
    if any(item in contextual for item in missing_inputs):
        return "context_required"
    if all(item in set(topology.execution_only_inputs) or item not in contextual for item in missing_inputs):
        return "execution_only"
    return "unknown"


def _classify_input_blocker_kind(blockers: tuple[str, ...], *, topology: WorkflowTopology | None) -> str | None:
    if not blockers:
        return None
    input_names: set[str] = set()
    for blocker in blockers:
        if not isinstance(blocker, str) or "inputs." not in blocker:
            continue
        for part in blocker.split("inputs.")[1:]:
            name = []
            for char in part:
                if char.isalnum() or char == "_":
                    name.append(char)
                else:
                    break
            if name:
                input_names.add("".join(name))
    if not input_names:
        return None
    return _classify_missing_input_kind(tuple(sorted(input_names)), topology=topology)


def _split_blockers(blockers: tuple[str, ...], *, missing_inputs: tuple[str, ...]) -> tuple[int, int]:
    if not blockers:
        return 0, 0
    input_blockers = 0
    world_blockers = 0
    missing_input_set = set(missing_inputs)
    for blocker in blockers:
        if not isinstance(blocker, str):
            continue
        if (
            blocker.startswith("inputs.")
            or blocker == "playbook.workflow.input_missing"
            or blocker == "playbook.workflow.input_unknown"
            or any(f"inputs.{name}" in blocker for name in missing_input_set)
        ):
            input_blockers += 1
            continue
        world_blockers += 1
    return input_blockers, world_blockers


def _classify_runtime_candidate(
    *,
    result: RuntimeResult,
    allowed: bool,
    reason_category: str | None,
    blockers: tuple[str, ...],
    matched_guard_count: int,
    relevant_guard_count: int,
    missing_inputs: tuple[str, ...],
    input_blocker_count: int,
    world_blocker_count: int,
    input_blocker_kind: str | None,
) -> str:
    if missing_inputs:
        return "awaiting_input"
    if input_blocker_count > 0 and world_blocker_count == 0 and input_blocker_kind == "execution_only":
        return "ready_with_execution_input"
    if allowed and result.status is RuntimeStatus.OK:
        return "ready_now"
    if result.status in {RuntimeStatus.VALIDATION_ERROR, RuntimeStatus.RESOLUTION_ERROR}:
        return "not_evaluable_now"
    if reason_category in {"workflow_profile", "bootstrap", "preflight_step", "incomplete", "validation", "resolution"}:
        return "not_evaluable_now"
    if relevant_guard_count > 0 and blockers:
        if matched_guard_count == 0:
            return "weak_match"
        if matched_guard_count * 2 < relevant_guard_count:
            return "weak_match"
    return "near_ready"


def _score_candidate(
    *,
    candidate_class: str,
    matched_guard_count: int,
    relevant_guard_count: int,
    full_evaluability: bool,
    blockers: tuple[str, ...],
    missing_inputs: tuple[str, ...],
    missing_input_kind: str | None,
    input_blocker_count: int,
    world_blocker_count: int,
    input_blocker_kind: str | None,
    reason_category: str | None,
) -> tuple[int, list[dict[str, object]]]:
    base_scores = {
        "ready_now": 1000,
        "context_inspector": 930,
        "ready_with_execution_input": 940,
        "near_ready_contextual": 760,
        "near_ready": 700,
        "awaiting_context_input": 500,
        "awaiting_input": 450,
        "not_evaluable_now": 300,
        "weak_match": 100,
    }
    class_messages = {
        "ready_now": "workflow is runnable now",
        "context_inspector": "workflow can inspect the already-established active context now",
        "ready_with_execution_input": "workflow is strongly indicated by current context and only lacks execution-only input",
        "near_ready_contextual": "workflow is structurally close to runnable inside the active context",
        "near_ready": "workflow is structurally close to runnable now",
        "awaiting_context_input": "workflow is context-related but still needs context-bearing input",
        "awaiting_input": "workflow is relevant but still needs caller input",
        "not_evaluable_now": "workflow could not be established safely enough from current evidence",
        "weak_match": "current context does not strongly match this workflow's guards",
    }
    score = base_scores[candidate_class]
    ratio_points = 0 if relevant_guard_count <= 0 else int((matched_guard_count / relevant_guard_count) * 100)
    factors: list[dict[str, object]] = [
        {
            "factor": "candidate_class",
            "effect": "bonus",
            "value": base_scores[candidate_class],
            "why": class_messages[candidate_class],
        }
    ]
    if matched_guard_count:
        guard_points = matched_guard_count * 20
        score += guard_points
        factors.append(
            {
                "factor": "matched_guard_count",
                "effect": "bonus",
                "value": guard_points,
                "why": f"{matched_guard_count} guard(s) already match the current context",
            }
        )
    if ratio_points:
        score += ratio_points
        factors.append(
            {
                "factor": "matched_guard_ratio",
                "effect": "bonus",
                "value": ratio_points,
                "why": f"{matched_guard_count} of {relevant_guard_count} relevant guard(s) currently match",
            }
        )
    if full_evaluability:
        score += 40
        factors.append(
            {
                "factor": "full_evaluability",
                "effect": "bonus",
                "value": 40,
                "why": "runtime could evaluate the workflow from current read-only evidence without major unknowns",
            }
        )
    if blockers:
        blocker_input_kind = missing_input_kind if missing_input_kind is not None else input_blocker_kind
        input_penalty_per = 10 if blocker_input_kind == "execution_only" else 25
        input_penalty = input_blocker_count * input_penalty_per
        world_penalty = world_blocker_count * 90
        if input_penalty:
            score -= input_penalty
            factors.append(
                {
                    "factor": "input_blockers",
                    "effect": "penalty",
                    "value": input_penalty,
                    "why": f"{input_blocker_count} blocker(s) depend on caller input rather than world state",
                }
            )
        if world_penalty:
            score -= world_penalty
            factors.append(
                {
                    "factor": "world_blockers",
                    "effect": "penalty",
                    "value": world_penalty,
                    "why": f"{world_blocker_count} blocker(s) indicate the current world state is not ready yet",
                }
            )
    if missing_inputs:
        penalty = len(missing_inputs) * (30 if missing_input_kind == "execution_only" else 80)
        score -= penalty
        factors.append(
            {
                "factor": "missing_inputs",
                "effect": "penalty",
                "value": penalty,
                "why": f"missing required input(s): {', '.join(missing_inputs)}",
            }
        )
    if candidate_class == "not_evaluable_now":
        score -= 50
        factors.append(
            {
                "factor": "non_evaluable_state",
                "effect": "penalty",
                "value": 50,
                "why": "runtime could not establish enough read-only evidence for a stronger recommendation",
            }
        )
    if reason_category in {"workflow_profile", "validation", "resolution"}:
        score -= 40
        factors.append(
            {
                "factor": "contract_issue",
                "effect": "penalty",
                "value": 40,
                "why": f"workflow is currently held back by {reason_category.replace('_', ' ')} issues",
            }
        )
    return score, factors


def _guard_counts(result: RuntimeResult) -> tuple[int, int, int]:
    decision = result.preflight_decision
    if decision is not None:
        relevant = [item for item in decision.guard_nodes if item.relevant]
        matched = [item for item in relevant if item.status == "passed"]
        evaluated = [item for item in relevant if item.evaluated]
        return len(matched), len(relevant), len(evaluated)
    relevant_guard_count = result.outputs.get("relevant_guard_count")
    evaluated_guard_count = result.outputs.get("evaluated_relevant_guard_count")
    guard_coverage = [item for item in result.outputs.get("guard_coverage", []) if isinstance(item, dict)]
    matched_guard_count = len([item for item in guard_coverage if item.get("status") == "passed"])
    return (
        matched_guard_count,
        relevant_guard_count if isinstance(relevant_guard_count, int) else len(guard_coverage),
        evaluated_guard_count if isinstance(evaluated_guard_count, int) else len([item for item in guard_coverage if item.get("evaluated")]),
    )


def _missing_inputs_from_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> tuple[str, ...]:
    names: list[str] = []
    for diagnostic in diagnostics:
        if diagnostic.code != "playbook.workflow.input_missing":
            continue
        value = diagnostic.details.get("input")
        if isinstance(value, str) and value not in names:
            names.append(value)
    return tuple(names)


def _diagnostic_reason_category(diagnostics: tuple[Diagnostic, ...]) -> str:
    if any(item.code == "playbook.profile.missing" for item in diagnostics):
        return "workflow_profile"
    if any(item.code == "playbook.workflow.input_unknown" for item in diagnostics):
        return "input_unknown"
    if diagnostics:
        first = diagnostics[0].code
        if first.startswith("playbook.workflow.working_directory"):
            return "working_directory"
        if first.startswith("playbook.workflow"):
            return "activation"
        if first.startswith("playbook.profile"):
            return "workflow_profile"
    return "activation"


def _recommendation_strength(best: NextCandidate, alternatives: list[NextCandidate]) -> str:
    if best.candidate_class in {"inspection_only", "ready_with_execution_input", "awaiting_context_input", "near_ready_contextual", "near_ready"}:
        return "weak"
    if not alternatives:
        return "strong"
    if abs(best.score - alternatives[0].score) < 40:
        return "competitive"
    return "strong"


def _class_order(candidate_class: str) -> int:
    order = {
        "ready_now": 0,
        "inspection_only": 1,
        "ready_with_execution_input": 1,
        "context_inspector": 2,
        "near_ready_contextual": 3,
        "near_ready": 4,
        "awaiting_context_input": 5,
        "awaiting_input": 6,
        "not_evaluable_now": 7,
        "weak_match": 8,
    }
    return order.get(candidate_class, 99)


def _semantic_precedence(candidate: NextCandidate, *, active_state_paths: tuple[str, ...]) -> int:
    has_active_state = bool(active_state_paths)
    in_state_cluster = bool(candidate.state_cluster)
    if has_active_state and in_state_cluster:
        if candidate.candidate_class == "ready_now" and candidate.world_blocker_count == 0 and candidate.state_role not in {"inspect", "utility"}:
            return 0
        if candidate.candidate_class == "ready_with_execution_input" and candidate.world_blocker_count == 0:
            return 1
        if candidate.candidate_class == "awaiting_context_input" and candidate.world_blocker_count == 0:
            return 2
        if candidate.candidate_class == "near_ready_contextual" and candidate.world_blocker_count == 0:
            return 3
        if candidate.candidate_class == "near_ready_contextual" and candidate.world_blocker_count > 0:
            return 4
        if candidate.candidate_class == "inspection_only":
            return 6
        return 5
    if has_active_state and candidate.candidate_class == "ready_now" and candidate.state_role == "utility":
        return 7
    return 8


def _candidate_class_adjustment(candidate_class: str) -> int:
    return {
        "ready_now": 0,
        "inspection_only": -120,
        "ready_with_execution_input": 40,
        "context_inspector": -70,
        "near_ready_contextual": 60,
        "near_ready": 0,
        "awaiting_context_input": 20,
        "awaiting_input": 0,
        "not_evaluable_now": 0,
        "weak_match": 0,
    }.get(candidate_class, 0)
