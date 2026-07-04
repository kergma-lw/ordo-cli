"""Check mode for pre-execution validation, resolution, and guard analysis."""

from __future__ import annotations

from typing import cast

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Workflow

from .guard_expressions import BinaryNode, CallNode, GuardExpressionNode, ListNode, LiteralNode, ReferenceNode, UnaryNode
from .profiles import apply_profile_to_workflow
from .providers import ConnectorProvider, GuardProbe, get_default_connector_provider
from .resolution import ResolvedExpressionProbe, ResolvedGuardExpression, ResolvedOperation, resolve_workflow_references
from .validation import validate_workflow_document


def check_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    guard_probe: GuardProbe | None = None,
    connector_provider: ConnectorProvider | None = None,
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
        connector_provider=connector_provider,
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

    probe = guard_probe or _default_guard_probe(provider=connector_provider)
    diagnostics: list[Diagnostic] = []
    operation_results: list[OperationResult] = []
    blockers: list[str] = []
    guard_details: list[dict[str, object]] = []
    bootstrap_details: list[dict[str, object]] = []
    failed_guard: str | None = None

    for resolved_guard in resolution.resolved_guards:
        if isinstance(resolved_guard, ResolvedGuardExpression):
            result = _evaluate_guard_expression(resolved_guard, effective_workflow, probe)
        else:
            result = probe(resolved_guard, effective_workflow)
        operation_results.append(result)
        diagnostics.extend(result.diagnostics)
        guard_details.append(_build_guard_detail(resolved_guard.reference, result))
        bootstrap_details = _collect_bootstrap_details(operation_results)
        if result.status != "ok":
            blockers.append(resolved_guard.reference)
            if failed_guard is None:
                failed_guard = resolved_guard.reference

    if blockers:
        outputs = {
            "can_execute": False,
            "blockers": blockers,
            "checked_guards": [result.reference for result in resolution.resolved_guards],
            "guard_details": guard_details,
            "active_profile": active_profile,
            "active_overrides": [override.to_contract() for override in active_overrides],
        }
        if bootstrap_details:
            outputs["bootstrap_details"] = bootstrap_details
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.GUARD_FAILED,
            diagnostics=tuple(diagnostics),
            plan=ExecutionPlan(
                guard_checks=tuple(result.reference for result in resolution.resolved_guards),
                step_names=tuple(step.name for step in effective_workflow.steps),
                blockers=tuple(blockers),
            ),
            outputs=outputs,
            operation_results=tuple(operation_results),
            failed_guard=failed_guard,
        )

    outputs = {
        "can_execute": True,
        "blockers": [],
        "checked_guards": [result.reference for result in resolution.resolved_guards],
        "guard_details": guard_details,
        "active_profile": active_profile,
        "active_overrides": [override.to_contract() for override in active_overrides],
    }
    if bootstrap_details:
        outputs["bootstrap_details"] = bootstrap_details

    return RuntimeResult(
        mode=Mode.CHECK,
        status=RuntimeStatus.OK,
        diagnostics=tuple(diagnostics),
        plan=ExecutionPlan(
            guard_checks=tuple(result.reference for result in resolution.resolved_guards),
            step_names=tuple(step.name for step in effective_workflow.steps),
            blockers=(),
        ),
        outputs=outputs,
        operation_results=tuple(operation_results),
    )


def _collect_bootstrap_details(operation_results: list[OperationResult]) -> list[dict[str, object]]:
    seen: set[str] = set()
    details: list[dict[str, object]] = []
    for result in operation_results:
        bootstrap = result.raw.get("bootstrap")
        if not isinstance(bootstrap, dict):
            continue
        namespace = bootstrap.get("namespace")
        if not isinstance(namespace, str) or namespace in seen:
            continue
        seen.add(namespace)
        details.append(
            {
                "namespace": namespace,
                "status": bootstrap.get("status"),
                "context": bootstrap.get("context", {}),
            }
        )
    return details


def _default_guard_probe(*, provider: ConnectorProvider | None):
    """Default side-effect-free probe backed by canonical connector operations."""

    def evaluate(resolved_guard: ResolvedOperation | ResolvedExpressionProbe, workflow: Workflow) -> OperationResult:
        resolved_provider = provider or get_default_connector_provider()
        return resolved_provider.guard_probe(resolved_guard, workflow)

    return evaluate


def _evaluate_guard_expression(
    resolved_guard: ResolvedGuardExpression,
    workflow: Workflow,
    probe: GuardProbe,
) -> OperationResult:
    cache: dict[str, tuple[str, JSONValue | None, OperationResult]] = {}
    diagnostics: list[Diagnostic] = []
    trace: list[dict[str, object]] = []

    def evaluate(node: GuardExpressionNode) -> tuple[str, JSONValue | None]:
        if isinstance(node, LiteralNode):
            value = cast(JSONValue, node.value)
            trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "literal", "status": "ok", "value": value})
            return "ok", value
        if isinstance(node, ListNode):
            values: list[JSONValue] = []
            for item in node.items:
                status, value = evaluate(item)
                if status != "ok":
                    return status, None
                values.append(cast(JSONValue, value))
            trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "list", "status": "ok", "value": values})
            return "ok", values
        if isinstance(node, ReferenceNode):
            if node.parts[0] == "inputs":
                status, value = _resolve_input_reference(node.parts, workflow, diagnostics)
                trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "input", "status": status, "value": value})
                return status, value
            probe_spec = _lookup_probe_spec(resolved_guard, resolved_guard.expr[node.start : node.end], tuple())
            status, value = _evaluate_probe_reference(probe_spec, probe, workflow, cache, diagnostics)
            trace.append({"expr": probe_spec.expression_text, "kind": "probe", "status": status, "value": value, "reference": probe_spec.reference})
            return status, value
        if isinstance(node, CallNode):
            probe_spec = _lookup_probe_spec(resolved_guard, resolved_guard.expr[node.start : node.end], node.fields)
            status, value = _evaluate_probe_reference(probe_spec, probe, workflow, cache, diagnostics)
            trace.append({"expr": probe_spec.expression_text, "kind": "probe", "status": status, "value": value, "reference": probe_spec.reference})
            return status, value
        if isinstance(node, UnaryNode):
            status, value = evaluate(node.operand)
            if status != "ok":
                return status, None
            result = not bool(value)
            trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "unary", "operator": node.operator, "status": "ok", "value": result})
            return "ok", result
        if isinstance(node, BinaryNode):
            if node.operator == "and":
                left_status, left_value = evaluate(node.left)
                if left_status != "ok":
                    return left_status, None
                if not bool(left_value):
                    trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "binary", "operator": node.operator, "status": "ok", "value": False})
                    return "ok", False
                right_status, right_value = evaluate(node.right)
                if right_status != "ok":
                    return right_status, None
                result = bool(right_value)
                trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "binary", "operator": node.operator, "status": "ok", "value": result})
                return "ok", result
            if node.operator == "or":
                left_status, left_value = evaluate(node.left)
                if left_status != "ok":
                    return left_status, None
                if bool(left_value):
                    trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "binary", "operator": node.operator, "status": "ok", "value": True})
                    return "ok", True
                right_status, right_value = evaluate(node.right)
                if right_status != "ok":
                    return right_status, None
                result = bool(right_value)
                trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "binary", "operator": node.operator, "status": "ok", "value": result})
                return "ok", result
            left_status, left_value = evaluate(node.left)
            if left_status != "ok":
                return left_status, None
            right_status, right_value = evaluate(node.right)
            if right_status != "ok":
                return right_status, None
            if node.operator == "==":
                result = left_value == right_value
                trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "binary", "operator": node.operator, "status": "ok", "value": result, "left": left_value, "right": right_value})
                return "ok", result
            if node.operator == "!=":
                result = left_value != right_value
                trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "binary", "operator": node.operator, "status": "ok", "value": result, "left": left_value, "right": right_value})
                return "ok", result
            if node.operator == "in":
                result = left_value in cast(object, right_value)
                trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "binary", "operator": node.operator, "status": "ok", "value": result, "left": left_value, "right": right_value})
                return "ok", result
            if node.operator == "not in":
                result = left_value not in cast(object, right_value)
                trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "binary", "operator": node.operator, "status": "ok", "value": result, "left": left_value, "right": right_value})
                return "ok", result
        return "probe_failed", None

    status, value = evaluate(resolved_guard.parsed.root)
    failed_trace = next((entry for entry in reversed(trace) if entry.get("status") == "probe_failed" or entry.get("value") is False), None)
    if status == "probe_failed":
        return OperationResult(
            status="probe_failed",
            summary="Guard expression could not be evaluated safely",
            diagnostics=tuple(diagnostics),
            outputs={"guard": resolved_guard.expr, "result": None, "failed_subcondition": None if failed_trace is None else failed_trace.get("expr")},
            raw={"cache_entries": len(cache), "trace": trace, "failure_kind": "probe_failed"},
        )
    passed = bool(value)
    return OperationResult(
        status="ok" if passed else "guard_failed",
        summary="Guard expression evaluated successfully" if passed else "Guard expression evaluated false",
        diagnostics=tuple(diagnostics),
        outputs={"guard": resolved_guard.expr, "result": passed, "failed_subcondition": None if passed or failed_trace is None else failed_trace.get("expr")},
        raw={"cache_entries": len(cache), "trace": trace, "failure_kind": "guard_failed" if not passed else None},
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

    value = _extract_probe_value(result.outputs, probe_spec.fields)
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


def _extract_probe_value(outputs: dict[str, JSONValue], fields: tuple[str, ...]) -> JSONValue | object:
    current: JSONValue = outputs
    if not fields:
        return current
    for field in fields:
        if not isinstance(current, dict) or field not in current:
            return _MISSING
        current = current[field]
    return current


def _build_guard_detail(reference: str, result: OperationResult) -> dict[str, object]:
    return {
        "reference": reference,
        "status": result.status,
        "summary": result.summary,
        "failed_subcondition": result.outputs.get("failed_subcondition"),
        "failure_kind": result.raw.get("failure_kind"),
        "trace": result.raw.get("trace", []),
    }
