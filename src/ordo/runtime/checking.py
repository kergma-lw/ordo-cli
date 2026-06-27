"""Check mode for pre-execution validation, resolution, and guard analysis."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Workflow

from .guard_expressions import BinaryNode, CallNode, GuardExpressionNode, ListNode, LiteralNode, ReferenceNode, UnaryNode
from .profiles import apply_profile_to_workflow
from .resolution import ResolvedExpressionProbe, ResolvedGuardExpression, ResolvedOperation, resolve_workflow_references
from .validation import validate_workflow_document

GuardProbe = Callable[[ResolvedOperation | ResolvedGuardExpression, Workflow], OperationResult]


def check_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    guard_probe: GuardProbe | None = None,
) -> RuntimeResult:
    """Run check mode without executing effectful business steps."""

    validation_report = validate_workflow_document(workflow.to_contract())
    if not validation_report.ok:
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.VALIDATION_ERROR,
            diagnostics=validation_report.diagnostics,
            plan=ExecutionPlan(),
            outputs={"can_execute": False, "blockers": [], "checked_guards": []},
        )

    active_profile = None
    active_overrides = ()
    effective_workflow = workflow

    if profile is not None:
        applied = apply_profile_to_workflow(workflow, profile)
        active_profile = applied.active_profile
        active_overrides = applied.active_overrides
        if not applied.ok or applied.workflow is None:
            return RuntimeResult(
                mode=Mode.CHECK,
                status=RuntimeStatus.VALIDATION_ERROR,
                diagnostics=applied.diagnostics,
                plan=ExecutionPlan(),
                outputs={
                    "can_execute": False,
                    "blockers": [],
                    "checked_guards": [],
                    "active_profile": active_profile,
                    "active_overrides": [override.to_contract() for override in active_overrides],
                },
            )
        effective_workflow = applied.workflow

    resolution = resolve_workflow_references(
        effective_workflow,
        active_overrides=active_overrides,
    )
    if not resolution.ok:
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.RESOLUTION_ERROR,
            diagnostics=resolution.diagnostics,
            plan=ExecutionPlan(
                guard_checks=tuple(guard.reference for guard in effective_workflow.guards),
                step_names=tuple(step.name for step in effective_workflow.steps),
                blockers=(),
            ),
            outputs={
                    "can_execute": False,
                    "blockers": [],
                    "checked_guards": [guard.reference for guard in effective_workflow.guards],
                    "active_profile": active_profile,
                    "active_overrides": [override.to_contract() for override in active_overrides],
                },
        )

    probe = guard_probe or _default_guard_probe
    diagnostics: list[Diagnostic] = []
    operation_results: list[OperationResult] = []
    blockers: list[str] = []
    failed_guard: str | None = None

    for resolved_guard in resolution.resolved_guards:
        if isinstance(resolved_guard, ResolvedGuardExpression):
            result = _evaluate_guard_expression(resolved_guard, effective_workflow, probe)
        else:
            result = probe(resolved_guard, effective_workflow)
        operation_results.append(result)
        diagnostics.extend(result.diagnostics)
        if result.status != "ok":
            blockers.append(resolved_guard.reference)
            if failed_guard is None:
                failed_guard = resolved_guard.reference

    if blockers:
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.GUARD_FAILED,
            diagnostics=tuple(diagnostics),
            plan=ExecutionPlan(
                guard_checks=tuple(result.reference for result in resolution.resolved_guards),
                step_names=tuple(step.name for step in effective_workflow.steps),
                blockers=tuple(blockers),
            ),
            outputs={
                "can_execute": False,
                "blockers": blockers,
                "checked_guards": [result.reference for result in resolution.resolved_guards],
                "active_profile": active_profile,
                "active_overrides": [override.to_contract() for override in active_overrides],
            },
            operation_results=tuple(operation_results),
            failed_guard=failed_guard,
        )

    return RuntimeResult(
        mode=Mode.CHECK,
        status=RuntimeStatus.OK,
        diagnostics=tuple(diagnostics),
        plan=ExecutionPlan(
            guard_checks=tuple(result.reference for result in resolution.resolved_guards),
            step_names=tuple(step.name for step in effective_workflow.steps),
            blockers=(),
        ),
        outputs={
            "can_execute": True,
            "blockers": [],
            "checked_guards": [result.reference for result in resolution.resolved_guards],
            "active_profile": active_profile,
            "active_overrides": [override.to_contract() for override in active_overrides],
        },
        operation_results=tuple(operation_results),
    )


def _default_guard_probe(resolved_guard: ResolvedOperation | ResolvedExpressionProbe, workflow: Workflow) -> OperationResult:
    """Default side-effect-free probe backed by canonical connector operations."""

    from ordo.connectors.operations import evaluate_probe

    return evaluate_probe(resolved_guard, workflow)


def _evaluate_guard_expression(
    resolved_guard: ResolvedGuardExpression,
    workflow: Workflow,
    probe: GuardProbe,
) -> OperationResult:
    cache: dict[str, tuple[str, JSONValue | None, OperationResult]] = {}
    diagnostics: list[Diagnostic] = []

    def evaluate(node: GuardExpressionNode) -> tuple[str, JSONValue | None]:
        if isinstance(node, LiteralNode):
            return "ok", cast(JSONValue, node.value)
        if isinstance(node, ListNode):
            values: list[JSONValue] = []
            for item in node.items:
                status, value = evaluate(item)
                if status != "ok":
                    return status, None
                values.append(cast(JSONValue, value))
            return "ok", values
        if isinstance(node, ReferenceNode):
            if node.parts[0] == "inputs":
                return _resolve_input_reference(node.parts, workflow, diagnostics)
            probe_spec = _lookup_probe_spec(resolved_guard, resolved_guard.expr[node.start : node.end], tuple())
            return _evaluate_probe_reference(probe_spec, probe, workflow, cache, diagnostics)
        if isinstance(node, CallNode):
            probe_spec = _lookup_probe_spec(resolved_guard, resolved_guard.expr[node.start : node.end], node.fields)
            return _evaluate_probe_reference(probe_spec, probe, workflow, cache, diagnostics)
        if isinstance(node, UnaryNode):
            status, value = evaluate(node.operand)
            if status != "ok":
                return status, None
            return "ok", not bool(value)
        if isinstance(node, BinaryNode):
            if node.operator == "and":
                left_status, left_value = evaluate(node.left)
                if left_status != "ok":
                    return left_status, None
                if not bool(left_value):
                    return "ok", False
                right_status, right_value = evaluate(node.right)
                if right_status != "ok":
                    return right_status, None
                return "ok", bool(right_value)
            if node.operator == "or":
                left_status, left_value = evaluate(node.left)
                if left_status != "ok":
                    return left_status, None
                if bool(left_value):
                    return "ok", True
                right_status, right_value = evaluate(node.right)
                if right_status != "ok":
                    return right_status, None
                return "ok", bool(right_value)
            left_status, left_value = evaluate(node.left)
            if left_status != "ok":
                return left_status, None
            right_status, right_value = evaluate(node.right)
            if right_status != "ok":
                return right_status, None
            if node.operator == "==":
                return "ok", left_value == right_value
            if node.operator == "!=":
                return "ok", left_value != right_value
            if node.operator == "in":
                return "ok", left_value in cast(object, right_value)
            if node.operator == "not in":
                return "ok", left_value not in cast(object, right_value)
        return "probe_failed", None

    status, value = evaluate(resolved_guard.parsed.root)
    if status == "probe_failed":
        return OperationResult(
            status="probe_failed",
            summary="Guard expression could not be evaluated safely",
            diagnostics=tuple(diagnostics),
            observations={"guard": resolved_guard.expr, "result": None},
            raw={"cache_entries": len(cache)},
        )
    passed = bool(value)
    return OperationResult(
        status="ok" if passed else "guard_failed",
        summary="Guard expression evaluated successfully" if passed else "Guard expression evaluated false",
        diagnostics=tuple(diagnostics),
        observations={"guard": resolved_guard.expr, "result": passed},
        raw={"cache_entries": len(cache)},
    )


def _resolve_input_reference(
    parts: tuple[str, ...],
    workflow: Workflow,
    diagnostics: list[Diagnostic],
) -> tuple[str, JSONValue | None]:
    current: JSONValue = workflow.inputs
    for part in parts[1:]:
        if not isinstance(current, dict) or part not in current:
            diagnostics.append(
                Diagnostic(
                    code="guard.input_missing",
                    level="error",
                    message=f"Workflow input '{'.'.join(parts)}' is missing",
                    path=(),
                    details={"input": ".".join(parts)},
                )
            )
            return "probe_failed", None
        current = current[part]
    return "ok", current


def _lookup_probe_spec(
    resolved_guard: ResolvedGuardExpression,
    expression_text: str,
    fallback_fields: tuple[str, ...],
) -> ResolvedExpressionProbe:
    for probe in resolved_guard.probes:
        if probe.expression_text == expression_text:
            return probe
    raise ValueError(f"Resolved probe metadata missing for expression segment: {expression_text} ({fallback_fields})")


def _evaluate_probe_reference(
    probe_spec: ResolvedExpressionProbe,
    probe: GuardProbe,
    workflow: Workflow,
    cache: dict[str, tuple[str, JSONValue | None, OperationResult]],
    diagnostics: list[Diagnostic],
) -> tuple[str, JSONValue | None]:
    cache_key = probe_spec.expression_text
    cached = cache.get(cache_key)
    if cached is not None:
        status, value, _ = cached
        return status, value

    result = probe(probe_spec, workflow)
    diagnostics.extend(result.diagnostics)
    if result.status != "ok":
        cache[cache_key] = ("probe_failed", None, result)
        return "probe_failed", None

    value = _extract_probe_value(result.observations, probe_spec.fields)
    if value is _MISSING:
        diagnostics.append(
            Diagnostic(
                code="guard.probe_field_missing",
                level="error",
                message=f"Probe field path '{'.'.join(probe_spec.fields)}' was not present at runtime",
                path=(),
                details={"reference": probe_spec.reference, "field_path": ".".join(probe_spec.fields)},
            )
        )
        cache[cache_key] = ("probe_failed", None, result)
        return "probe_failed", None

    cache[cache_key] = ("ok", value, result)
    return "ok", value


_MISSING = object()


def _extract_probe_value(observations: dict[str, JSONValue], fields: tuple[str, ...]) -> JSONValue | object:
    current: JSONValue = observations
    if not fields:
        return current
    for field in fields:
        if not isinstance(current, dict) or field not in current:
            return _MISSING
        current = current[field]
    return current
