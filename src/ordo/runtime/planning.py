"""Plan mode for structured pre-execution visibility."""

from __future__ import annotations

from collections.abc import Callable

from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Workflow

from .checking import GuardProbe, check_workflow
from .profiles import apply_profile_to_workflow
from .resolution import WorkflowResolution, resolve_workflow_references
from .validation import validate_workflow_document


def plan_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    guard_probe: GuardProbe | None = None,
) -> RuntimeResult:
    """Build a structured plan without executing effectful business steps."""

    check_result = check_workflow(workflow, profile=profile, guard_probe=guard_probe)
    base_outputs = dict(check_result.outputs)
    effective_workflow = workflow

    if profile is not None:
        applied = apply_profile_to_workflow(workflow, profile)
        if applied.ok and applied.workflow is not None:
            effective_workflow = applied.workflow

    validation_report = validate_workflow_document(effective_workflow.to_contract())
    resolution: WorkflowResolution | None = None
    if validation_report.ok:
        resolution = resolve_workflow_references(
            effective_workflow,
            active_overrides=tuple(profile.overrides) if profile is not None else (),
        )

    guard_items = _build_guard_items(check_result, resolution)
    step_items = _build_step_items(check_result, resolution, effective_workflow)

    blockers = list(base_outputs.get("blockers", []))
    can_execute = bool(base_outputs.get("can_execute", False))

    plan = ExecutionPlan(
        guard_checks=tuple(item["reference"] for item in guard_items),
        step_names=tuple(item["name"] for item in step_items),
        blockers=tuple(blockers),
    )

    outputs = {
        **base_outputs,
        "plan_ready": check_result.status is not RuntimeStatus.VALIDATION_ERROR,
        "execution_allowed": can_execute,
        "guard_items": guard_items,
        "step_items": step_items,
    }

    return RuntimeResult(
        mode=Mode.PLAN,
        status=check_result.status,
        diagnostics=check_result.diagnostics,
        plan=plan,
        outputs=outputs,
        operation_results=check_result.operation_results,
        failed_guard=check_result.failed_guard,
        failed_step=check_result.failed_step,
    )


def _build_guard_items(check_result: RuntimeResult, resolution: WorkflowResolution | None) -> list[dict[str, object]]:
    guard_items: list[dict[str, object]] = []

    if resolution is not None and resolution.resolved_guards:
        for index, resolved_guard in enumerate(resolution.resolved_guards):
            operation_result = check_result.operation_results[index] if index < len(check_result.operation_results) else None
            guard_items.append(
                {
                    "reference": resolved_guard.reference,
                    "kind": resolved_guard.operation.kind,
                    "effect": "read_only" if resolved_guard.operation.kind == "probe" else "effectful",
                    "status": "blocked" if resolved_guard.reference in check_result.outputs.get("blockers", []) else "ok",
                    "operation_status": None if operation_result is None else operation_result.status,
                }
            )
        return guard_items

    for reference in check_result.outputs.get("checked_guards", []):
        guard_items.append(
            {
                "reference": reference,
                "kind": "probe_or_expr",
                "effect": "read_only",
                "status": "blocked" if reference in check_result.outputs.get("blockers", []) else "unknown",
                "operation_status": None,
            }
        )
    return guard_items


def _build_step_items(
    check_result: RuntimeResult,
    resolution: WorkflowResolution | None,
    workflow: Workflow,
) -> list[dict[str, object]]:
    blocked = bool(check_result.outputs.get("blockers"))
    step_items: list[dict[str, object]] = []

    if resolution is not None and resolution.resolved_steps:
        for step, resolved_step in zip(workflow.steps, resolution.resolved_steps, strict=False):
            step_items.append(
                {
                    "name": step.name,
                    "reference": resolved_step.reference,
                    "kind": resolved_step.operation.kind,
                    "effect": "read_only" if resolved_step.operation.kind == "probe" else "effectful",
                    "eligibility": "blocked" if blocked else "eligible",
                }
            )
        return step_items

    for step in workflow.steps:
        step_items.append(
            {
                "name": step.name,
                "reference": step.operation.uses,
                "kind": "unknown",
                "effect": "unknown",
                "eligibility": "blocked" if blocked else "unknown",
            }
        )
    return step_items
