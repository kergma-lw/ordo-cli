"""Check mode for pre-execution validation, resolution, and guard analysis."""

from __future__ import annotations

from typing import cast

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import GuardBlock, StepBlock, Workflow

from .guard_expressions import BinaryNode, CallNode, GuardExpressionNode, ListNode, LiteralNode, ReferenceNode, StateReferenceNode, UnaryNode
from .state import RuntimeStateError, read_state_document, read_state_value, resolve_state_target
from .launchers import validate_step_launchers
from .profiles import apply_profile_to_workflow
from .providers import ConnectorProvider, GuardProbe, get_default_connector_provider
from .resolution import ResolvedExpressionProbe, ResolvedGuardBlock, ResolvedGuardExpression, ResolvedOperation, ResolvedStepBlock, resolve_workflow_references
from .validation import validate_workflow_document


def _base_verdict_outputs(
    *,
    can_execute: bool,
    allowed_state: str,
    analysis_complete: bool,
    incomplete_reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "can_execute": can_execute,
        "allowed_state": allowed_state,
        "analysis_complete": analysis_complete,
        "incomplete_reasons": [] if incomplete_reasons is None else list(incomplete_reasons),
    }


def _guard_coverage_outputs(
    workflow: Workflow,
    *,
    checked_guards: list[str],
    blockers: list[str],
) -> dict[str, object]:
    checked = set(checked_guards)
    blocked = set(blockers)
    coverage: list[dict[str, object]] = []
    unevaluated: list[str] = []
    for reference in _all_guard_references(workflow):
        if reference in checked:
            coverage.append(
                {
                    "reference": reference,
                    "relevant": True,
                    "evaluated": True,
                    "status": "blocked" if reference in blocked else "passed",
                    "unknown_reason": None,
                }
            )
            continue
        unevaluated.append(reference)
        coverage.append(
            {
                "reference": reference,
                "relevant": True,
                "evaluated": False,
                "status": "pending",
                "unknown_reason": "guard_not_evaluated",
            }
        )
    return {
        "guard_coverage": coverage,
        "relevant_guard_count": len(coverage),
        "evaluated_relevant_guard_count": len(checked_guards),
        "unevaluated_relevant_guard_count": len(unevaluated),
        "unevaluated_relevant_guards": unevaluated,
    }


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
            outputs={
                **_base_verdict_outputs(can_execute=False, allowed_state="blocked", analysis_complete=True),
                "blockers": [],
                "checked_guards": [],
                "guard_coverage": [],
                "relevant_guard_count": 0,
                "evaluated_relevant_guard_count": 0,
                "unevaluated_relevant_guard_count": 0,
                "unevaluated_relevant_guards": [],
                "block_items": [],
            },
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
                    **_base_verdict_outputs(can_execute=False, allowed_state="blocked", analysis_complete=True),
                    "blockers": [],
                    "checked_guards": [],
                    "guard_coverage": [],
                    "relevant_guard_count": 0,
                    "evaluated_relevant_guard_count": 0,
                    "unevaluated_relevant_guard_count": 0,
                    "unevaluated_relevant_guards": [],
                    "block_items": [],
                    "active_profile": active_profile,
                    "active_overrides": [override.to_contract() for override in active_overrides],
                },
            )
        effective_workflow = applied.workflow

    launcher_diagnostics = validate_step_launchers(effective_workflow, active_profile, {} if profile is None else profile.launchers)
    if launcher_diagnostics:
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.VALIDATION_ERROR,
            diagnostics=launcher_diagnostics,
            plan=ExecutionPlan(),
            outputs={
                **_base_verdict_outputs(can_execute=False, allowed_state="blocked", analysis_complete=True),
                "blockers": [],
                "checked_guards": [],
                **_guard_coverage_outputs(effective_workflow, checked_guards=[], blockers=[]),
                "block_items": _build_pending_block_items(effective_workflow, blocked=False),
                "active_profile": active_profile,
                "active_overrides": [override.to_contract() for override in active_overrides],
            },
        )

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
                guard_checks=tuple(_initial_guard_references(effective_workflow)),
                step_names=tuple(_all_step_names(effective_workflow)),
                blockers=(),
            ),
            outputs={
                **_base_verdict_outputs(can_execute=False, allowed_state="blocked", analysis_complete=True),
                "blockers": [],
                "checked_guards": list(_initial_guard_references(effective_workflow)),
                **_guard_coverage_outputs(
                    effective_workflow,
                    checked_guards=list(_initial_guard_references(effective_workflow)),
                    blockers=[],
                ),
                "block_items": _build_pending_block_items(effective_workflow, blocked=False),
                "active_profile": active_profile,
                "active_overrides": [override.to_contract() for override in active_overrides],
            },
        )

    probe = guard_probe or _default_guard_probe(provider=connector_provider)
    diagnostics: list[Diagnostic] = []
    operation_results: list[OperationResult] = []
    blockers: list[str] = []
    checked_guards: list[str] = []
    guard_details: list[dict[str, object]] = []
    block_items: list[dict[str, object]] = []
    bootstrap_details: list[dict[str, object]] = []
    failed_guard: str | None = None
    incomplete_reasons: list[str] = []

    halted = False
    for block in resolution.blocks:
        if isinstance(block, ResolvedGuardBlock):
            if halted:
                block_items.append(_pending_guard_block_item(block, effective_workflow))
                continue
            block_blockers: list[str] = []
            block_guard_details: list[dict[str, object]] = []
            for resolved_guard in block.guards:
                if isinstance(resolved_guard, ResolvedGuardExpression):
                    result = _evaluate_guard_expression(resolved_guard, effective_workflow, probe)
                else:
                    result = probe(resolved_guard, effective_workflow)
                operation_results.append(result)
                diagnostics.extend(result.diagnostics)
                detail = _build_guard_detail(resolved_guard.reference, result)
                guard_details.append(detail)
                block_guard_details.append(detail)
                checked_guards.append(resolved_guard.reference)
                bootstrap_details = _collect_bootstrap_details(operation_results)
                if result.status != "ok":
                    blockers.append(resolved_guard.reference)
                    block_blockers.append(resolved_guard.reference)
                    if failed_guard is None:
                        failed_guard = resolved_guard.reference
            block_items.append(
                {
                    "block_index": block.block_index,
                    "type": "guards",
                    "status": "blocked" if block_blockers else "ok",
                    "guard_references": [guard.reference for guard in block.guards],
                    "blockers": block_blockers,
                    "guard_details": block_guard_details,
                }
            )
            if block_blockers:
                halted = True
            continue

        if halted:
            block_items.append(_pending_step_block_item(block, effective_workflow, blocked=True))
            continue
        block_items.append(_pending_step_block_item(block, effective_workflow, blocked=False))
        halted = True

    if not blockers and any(item.get("type") == "guards" and item.get("status") == "pending" for item in block_items):
        incomplete_reasons.append("relevant_guard_coverage_incomplete")
        if _has_pre_run_before_pending_guards(block_items):
            incomplete_reasons.append("pre_run_precedes_main_guard_coverage")

    if halted and len(block_items) < len(effective_workflow.blocks):
        block_items.extend(_build_pending_block_items(effective_workflow, blocked=bool(blockers), start_index=len(block_items)))

    if blockers:
        outputs = {
            **_base_verdict_outputs(can_execute=False, allowed_state="blocked", analysis_complete=True),
            "blockers": blockers,
            "checked_guards": checked_guards,
            **_guard_coverage_outputs(effective_workflow, checked_guards=checked_guards, blockers=blockers),
            "guard_details": guard_details,
            "block_items": block_items,
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
                guard_checks=tuple(checked_guards),
                step_names=tuple(_all_step_names(effective_workflow)),
                blockers=tuple(blockers),
            ),
            outputs=outputs,
            operation_results=tuple(operation_results),
            failed_guard=failed_guard,
        )

    outputs = {
        **_base_verdict_outputs(
            can_execute=not incomplete_reasons,
            allowed_state="unknown" if incomplete_reasons else "allowed",
            analysis_complete=not incomplete_reasons,
            incomplete_reasons=incomplete_reasons,
        ),
        "blockers": [],
        "checked_guards": checked_guards,
        **_guard_coverage_outputs(effective_workflow, checked_guards=checked_guards, blockers=[]),
        "guard_details": guard_details,
        "block_items": block_items,
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
            guard_checks=tuple(checked_guards),
            step_names=tuple(_all_step_names(effective_workflow)),
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


def _all_step_names(workflow: Workflow) -> list[str]:
    return [step.name for block in workflow.blocks if isinstance(block, StepBlock) for step in block.steps]


def _all_guard_references(workflow: Workflow) -> list[str]:
    return [guard.reference for block in workflow.blocks if isinstance(block, GuardBlock) for guard in block.guards]


def _initial_guard_references(workflow: Workflow) -> list[str]:
    references: list[str] = []
    for block in workflow.blocks:
        if isinstance(block, StepBlock):
            break
        references.extend(guard.reference for guard in block.guards)
    return references


def _build_pending_block_items(workflow: Workflow, *, blocked: bool, start_index: int = 0) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for block_index, block in enumerate(workflow.blocks[start_index:], start=start_index):
        if isinstance(block, GuardBlock):
            items.append(
                {
                    "block_index": block_index,
                    "type": "guards",
                    "status": "pending",
                    "guard_references": [guard.reference for guard in block.guards],
                    "blockers": [],
                    "guard_details": [],
                }
            )
        else:
            assert isinstance(block, StepBlock)
            items.append(
                {
                    "block_index": block_index,
                    "type": "steps",
                    "status": "blocked" if blocked else "pending",
                    "step_names": [step.name for step in block.steps],
                    "conditional_steps": [step.name for step in block.steps if step.if_ is not None],
                }
            )
    return items


def _pending_guard_block_item(block: ResolvedGuardBlock, workflow: Workflow) -> dict[str, object]:
    declared = workflow.blocks[block.block_index]
    assert isinstance(declared, GuardBlock)
    return {
        "block_index": block.block_index,
        "type": "guards",
        "status": "pending",
        "guard_references": [guard.reference for guard in declared.guards],
        "blockers": [],
        "guard_details": [],
    }


def _pending_step_block_item(block: ResolvedStepBlock, workflow: Workflow, *, blocked: bool) -> dict[str, object]:
    declared = workflow.blocks[block.block_index]
    assert isinstance(declared, StepBlock)
    return {
        "block_index": block.block_index,
        "type": "steps",
        "status": "blocked" if blocked else "pending",
        "step_names": [step.name for step in declared.steps],
        "conditional_steps": [step.name for step in declared.steps if step.if_ is not None],
    }


def _has_pre_run_before_pending_guards(block_items: list[dict[str, object]]) -> bool:
    saw_pre_run = False
    for item in block_items:
        if item.get("type") == "steps":
            step_names = item.get("step_names")
            if isinstance(step_names, list) and any(isinstance(name, str) and name.startswith("pre_run[") for name in step_names):
                saw_pre_run = True
                continue
        if saw_pre_run and item.get("type") == "guards" and item.get("status") == "pending":
            return True
    return False


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
        if isinstance(node, StateReferenceNode):
            status, value = _resolve_state_reference(node, resolved_guard, workflow, diagnostics)
            trace.append({"expr": resolved_guard.expr[node.start : node.end], "kind": "state", "status": status, "value": value})
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


def _resolve_state_reference(
    node: StateReferenceNode,
    resolved_guard: ResolvedGuardExpression,
    workflow: Workflow,
    diagnostics: list[Diagnostic],
) -> tuple[str, JSONValue | None]:
    expression = resolved_guard.expr[node.start : node.end]
    try:
        target = resolve_state_target(expression, workflow)
        document = read_state_document(target.location)
        value = read_state_value(document, key=target.key, fields=target.fields)
    except RuntimeStateError as exc:
        diagnostics.append(exc.to_diagnostic())
        return "probe_failed", None
    if value is None:
        diagnostics.append(
            Diagnostic(
                code="runtime.state.read_missing",
                level="error",
                message="Runtime state value is missing",
                path=(),
                details={"expression": expression, "state": target.location.name, "key": target.key, "fields": list(target.fields)},
            )
        )
        return "probe_failed", None
    return "ok", value


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
