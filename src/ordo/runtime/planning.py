"""Plan mode for structured pre-execution visibility."""

from __future__ import annotations

from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import GuardBlock, StepBlock, Workflow

from .checking import check_workflow
from .providers import ConnectorProvider, GuardProbe
from .profiles import apply_profile_to_workflow
from .resolution import ResolvedBuiltinStep, ResolvedGuardBlock, ResolvedGuardExpression, ResolvedRunStep, ResolvedStepBlock, WorkflowResolution, resolve_workflow_references
from .validation import validate_workflow_document


def plan_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    guard_probe: GuardProbe | None = None,
    connector_provider: ConnectorProvider | None = None,
) -> RuntimeResult:
    """Build a structured plan without executing effectful business steps."""

    check_result = check_workflow(workflow, profile=profile, guard_probe=guard_probe, connector_provider=connector_provider)
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
            connector_provider=connector_provider,
            active_overrides=tuple(profile.overrides) if profile is not None else (),
        )

    guard_items = _build_guard_items(check_result, resolution)
    step_items = _build_step_items(check_result, resolution, effective_workflow)
    run_items = _build_run_items(check_result, resolution, effective_workflow)
    block_items = _build_block_items(check_result, resolution, effective_workflow)

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
        "run_items": run_items,
        "block_items": block_items,
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
            if isinstance(resolved_guard, ResolvedGuardExpression):
                detail = check_result.outputs.get("guard_details", [])[index] if index < len(check_result.outputs.get("guard_details", [])) else {}
                guard_items.append(
                    {
                        "reference": resolved_guard.reference,
                        "kind": "expression",
                        "effect": "read_only",
                        "status": "blocked" if resolved_guard.reference in check_result.outputs.get("blockers", []) else "unknown",
                        "operation_status": None if operation_result is None else operation_result.status,
                        "failed_subcondition": detail.get("failed_subcondition") if isinstance(detail, dict) else None,
                        "failure_kind": detail.get("failure_kind") if isinstance(detail, dict) else None,
                    }
                )
                continue
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
            if isinstance(resolved_step, ResolvedBuiltinStep):
                step_items.append(
                    {
                        "name": step.name,
                        "reference": resolved_step.reference,
                        "kind": "builtin",
                        "effect": "effectful",
                        "eligibility": "blocked" if blocked else "eligible",
                        "conditional": step.if_ is not None,
                        "condition": step.if_,
                        "launcher": step.launcher,
                    }
                )
                continue
            if isinstance(resolved_step, ResolvedRunStep):
                step_items.append(
                    {
                        "name": step.name,
                        "reference": resolved_step.reference,
                        "kind": "run",
                        "effect": "effectful",
                        "eligibility": "blocked" if blocked else "eligible",
                        "conditional": step.if_ is not None,
                        "condition": step.if_,
                        "launcher": None,
                    }
                )
                continue
            step_items.append(
                {
                    "name": step.name,
                    "reference": resolved_step.reference,
                    "kind": resolved_step.operation.kind,
                    "effect": "read_only" if resolved_step.operation.kind == "probe" else "effectful",
                    "eligibility": "blocked" if blocked else "eligible",
                    "conditional": step.if_ is not None,
                    "condition": step.if_,
                    "launcher": step.launcher,
                }
            )
        return step_items

    for step in workflow.steps:
        step_items.append(
            {
                "name": step.name,
                "reference": step.operation.uses if step.operation is not None else step.run if step.run is not None else "builtin",
                "kind": "unknown" if step.operation is not None or step.run is not None else "builtin",
                "effect": "unknown" if step.operation is not None or step.run is not None else "effectful",
                "eligibility": "blocked" if blocked else "unknown",
                "conditional": step.if_ is not None,
                "condition": step.if_,
                "launcher": step.launcher if step.operation is not None else None,
            }
        )
    return step_items


def _build_block_items(
    check_result: RuntimeResult,
    resolution: WorkflowResolution | None,
    workflow: Workflow,
) -> list[dict[str, object]]:
    existing = [dict(item) for item in check_result.outputs.get("block_items", []) if isinstance(item, dict)]
    if resolution is None:
        return existing

    existing_by_index = {item.get("block_index"): item for item in existing if isinstance(item.get("block_index"), int)}
    block_items: list[dict[str, object]] = []

    first_reachable_step_found = False
    for block_index, (declared_block, resolved_block) in enumerate(zip(workflow.blocks, resolution.blocks, strict=False)):
        current = existing_by_index.get(block_index)
        if isinstance(declared_block, GuardBlock):
            if current is not None:
                block_items.append(current)
                continue
            assert isinstance(resolved_block, ResolvedGuardBlock)
            block_items.append(
                {
                    "block_index": block_index,
                    "type": "guards",
                    "status": "pending",
                    "guard_references": [guard.reference for guard in resolved_block.guards],
                    "blockers": [],
                    "guard_details": [],
                }
            )
            continue

        assert isinstance(declared_block, StepBlock)
        if current is not None:
            item = dict(current)
            if item.get("status") == "pending":
                item["eligibility"] = "eligible" if not first_reachable_step_found and not check_result.outputs.get("blockers") else "pending"
            block_items.append(item)
            first_reachable_step_found = True
            continue

        assert isinstance(resolved_block, ResolvedStepBlock)
        step_names = [step.name for step in declared_block.steps]
        block_items.append(
            {
                "block_index": block_index,
                "type": "steps",
                "status": "pending",
                "eligibility": "eligible" if not first_reachable_step_found and not check_result.outputs.get("blockers") else "pending",
                "step_names": step_names,
                "conditional_steps": [step.name for step in declared_block.steps if step.if_ is not None],
            }
        )
        first_reachable_step_found = True

    return block_items


def _build_run_items(
    check_result: RuntimeResult,
    resolution: WorkflowResolution | None,
    workflow: Workflow,
) -> list[dict[str, object]]:
    blocked = bool(check_result.outputs.get("blockers"))
    run_items: list[dict[str, object]] = []
    for step in workflow.steps:
        if step.run is None:
            continue
        run_items.append(
            {
                "name": step.name,
                "reference": step.run,
                "eligibility": "blocked" if blocked else "eligible",
                "conditional": step.if_ is not None,
                "condition": step.if_,
            }
        )
        blocked = True
    return run_items
