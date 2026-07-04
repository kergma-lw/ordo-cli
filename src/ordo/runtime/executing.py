"""Minimal contract-first execute mode."""

from __future__ import annotations

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Workflow

from .checking import GuardProbe, check_workflow
from .profiles import apply_profile_to_workflow
from .providers import ConnectorProvider, StepExecutor, get_default_connector_provider
from .resolution import ResolvedBuiltinStep, ResolvedOperation, resolve_workflow_references
from .state import RuntimeStateError, delete_state_value, read_state_document, resolve_state_target, write_state_document, write_state_value
from .value_resolution import ValueResolutionError, resolve_runtime_value


def execute_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    guard_probe: GuardProbe | None = None,
    step_executor: StepExecutor | None = None,
    connector_provider: ConnectorProvider | None = None,
) -> RuntimeResult:
    """Execute steps only after validation, resolution, and guards succeed."""

    check_result = check_workflow(workflow, profile=profile, guard_probe=guard_probe, connector_provider=connector_provider)
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

    resolution = resolve_workflow_references(effective_workflow, connector_provider=connector_provider, active_overrides=active_overrides)
    executor = step_executor or _default_step_executor(provider=connector_provider)
    diagnostics: list[Diagnostic] = list(check_result.diagnostics)
    operation_results: list[OperationResult] = list(check_result.operation_results)
    executed_steps: list[str] = []
    skipped_steps: list[str] = []
    effective_workflow.step_results.clear()

    for step, resolved_step in zip(effective_workflow.steps, resolution.resolved_steps, strict=False):
        if isinstance(resolved_step, ResolvedBuiltinStep):
            result = _execute_builtin_state_step(step, effective_workflow)
        else:
            result = executor(resolved_step, effective_workflow)
        if step.register is not None:
            effective_workflow.step_results[step.register] = {
                "status": result.status,
                "summary": result.summary,
                "outputs": dict(result.outputs),
            }
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


def _default_step_executor(*, provider: ConnectorProvider | None):
    """Default executor backed by canonical connector operations."""

    def execute(resolved_step: ResolvedOperation, workflow: Workflow) -> OperationResult:
        resolved_provider = provider or get_default_connector_provider()
        return resolved_provider.step_executor(resolved_step, workflow)

    return execute


def _execute_builtin_state_step(step, workflow: Workflow) -> OperationResult:
    try:
        if step.state_set is not None:
            return _execute_state_set(step.name, step.state_set, workflow)
        if step.state_delete is not None:
            return _execute_state_delete(step.name, step.state_delete, workflow)
    except RuntimeStateError as exc:
        return OperationResult(status="state_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))
    except ValueResolutionError as exc:
        return OperationResult(status="state_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))
    return OperationResult(status="state_error", summary="Unknown builtin step form")


def _execute_state_set(step_name: str, state_set: dict[str, JSONValue], workflow: Workflow) -> OperationResult:
    target_expr, raw_value = next(iter(state_set.items()))
    target = resolve_state_target(target_expr, workflow)
    value = resolve_runtime_value(raw_value, workflow)
    document = read_state_document(target.location)
    write_state_value(document, key=target.key, fields=target.fields, value=value)
    write_state_document(target.location, document)
    return OperationResult(
        status="ok",
        summary=f"Stored runtime state for step '{step_name}'",
        outputs={
            "state": target.location.name,
            "key": target.key,
            "fields": list(target.fields),
            "written": True,
        },
    )


def _execute_state_delete(step_name: str, target_expr: str, workflow: Workflow) -> OperationResult:
    target = resolve_state_target(target_expr, workflow)
    document = read_state_document(target.location)
    deleted = delete_state_value(document, key=target.key, fields=target.fields)
    write_state_document(target.location, document)
    return OperationResult(
        status="ok",
        summary=(
            f"Deleted runtime state for step '{step_name}'"
            if deleted
            else f"Runtime state target for step '{step_name}' was already absent"
        ),
        outputs={
            "state": target.location.name,
            "key": target.key,
            "fields": list(target.fields),
            "deleted": deleted,
        },
    )
