"""Minimal contract-first execute mode."""

from __future__ import annotations

from collections.abc import Callable

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Workflow

from .checking import GuardProbe, check_workflow
from .profiles import apply_profile_to_workflow
from .resolution import ResolvedOperation, resolve_workflow_references

StepExecutor = Callable[[ResolvedOperation, Workflow], OperationResult]


def execute_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    guard_probe: GuardProbe | None = None,
    step_executor: StepExecutor | None = None,
) -> RuntimeResult:
    """Execute steps only after validation, resolution, and guards succeed."""

    check_result = check_workflow(workflow, profile=profile, guard_probe=guard_probe)
    if check_result.status is not RuntimeStatus.OK:
        return RuntimeResult(
            mode=Mode.EXECUTE,
            status=check_result.status,
            diagnostics=check_result.diagnostics,
            plan=check_result.plan,
            outputs={
                **dict(check_result.outputs),
                "executed_steps": [],
                "skipped_steps": [step.name for step in workflow.steps],
            },
            operation_results=check_result.operation_results,
            failed_guard=check_result.failed_guard,
            failed_step=check_result.failed_step,
        )

    effective_workflow = workflow
    active_profile = None
    active_overrides = ()
    if profile is not None:
        applied = apply_profile_to_workflow(workflow, profile)
        if applied.ok and applied.workflow is not None:
            effective_workflow = applied.workflow
            active_profile = applied.active_profile
            active_overrides = applied.active_overrides

    resolution = resolve_workflow_references(effective_workflow, active_overrides=active_overrides)
    executor = step_executor or _default_step_executor
    diagnostics: list[Diagnostic] = list(check_result.diagnostics)
    operation_results: list[OperationResult] = list(check_result.operation_results)
    executed_steps: list[str] = []
    skipped_steps: list[str] = []

    for step, resolved_step in zip(effective_workflow.steps, resolution.resolved_steps, strict=False):
        result = executor(resolved_step, effective_workflow)
        operation_results.append(result)
        diagnostics.extend(result.diagnostics)

        if result.status != "ok":
            skipped_steps.extend(remaining.name for remaining in effective_workflow.steps[len(executed_steps) + 1 :])
            return RuntimeResult(
                mode=Mode.EXECUTE,
                status=RuntimeStatus.EXECUTION_ERROR,
                diagnostics=tuple(diagnostics),
                plan=check_result.plan,
                outputs={
                    "can_execute": False,
                    "active_profile": active_profile,
                    "active_overrides": [override.to_contract() for override in active_overrides],
                    "executed_steps": executed_steps,
                    "skipped_steps": skipped_steps,
                },
                operation_results=tuple(operation_results),
                failed_step=step.name,
            )

        executed_steps.append(step.name)

    return RuntimeResult(
        mode=Mode.EXECUTE,
        status=RuntimeStatus.OK,
        diagnostics=tuple(diagnostics),
        plan=check_result.plan,
        outputs={
            "can_execute": True,
            "active_profile": active_profile,
            "active_overrides": [override.to_contract() for override in active_overrides],
            "executed_steps": executed_steps,
            "skipped_steps": skipped_steps,
        },
        operation_results=tuple(operation_results),
    )


def _default_step_executor(resolved_step: ResolvedOperation, workflow: Workflow) -> OperationResult:
    """Default executor backed by canonical connector operations."""

    from ordo.connectors.operations import execute_action

    return execute_action(resolved_step, workflow)
