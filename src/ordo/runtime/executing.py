"""Minimal contract-first execute mode."""

from __future__ import annotations

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import GuardBlock, RunBlock, Step, StepBlock, Workflow

from .checking import GuardProbe, _build_guard_detail, _default_guard_probe, _evaluate_guard_expression, check_workflow
from .fragment_runs import evaluate_run_condition, materialize_run_workflow
from .launchers import apply_launcher_to_step
from .profiles import apply_profile_to_workflow
from .providers import ConnectorProvider, StepExecutor, get_default_connector_provider
from .resolution import ResolvedBuiltinStep, ResolvedGuardBlock, ResolvedGuardExpression, ResolvedOperation, ResolvedRunBlock, ResolvedStepBlock, resolve_workflow_references
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
                "skipped_steps": _all_step_names(workflow),
                "step_condition_details": [],
                "launcher_details": [],
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
    step_condition_details: list[dict[str, object]] = []
    launcher_details: list[dict[str, object]] = []
    block_items: list[dict[str, object]] = [dict(item) for item in check_result.outputs.get("block_items", []) if isinstance(item, dict)]
    guard_details: list[dict[str, object]] = [dict(item) for item in check_result.outputs.get("guard_details", []) if isinstance(item, dict)]
    checked_guards: list[str] = list(check_result.outputs.get("checked_guards", []))
    effective_workflow.step_results.clear()

    start_block_index = _initial_checked_block_count(effective_workflow)

    for block_index, (declared_block, resolved_block) in enumerate(zip(effective_workflow.blocks, resolution.blocks, strict=False)):
        if block_index < start_block_index:
            continue

        if isinstance(declared_block, GuardBlock):
            assert isinstance(resolved_block, ResolvedGuardBlock)
            block_blockers: list[str] = []
            block_guard_details: list[dict[str, object]] = []
            for resolved_guard in resolved_block.guards:
                if isinstance(resolved_guard, ResolvedGuardExpression):
                    result = _evaluate_guard_expression(resolved_guard, effective_workflow, guard_probe or _default_guard_probe(provider=connector_provider))
                else:
                    result = (guard_probe or _default_guard_probe(provider=connector_provider))(resolved_guard, effective_workflow)
                operation_results.append(result)
                diagnostics.extend(result.diagnostics)
                detail = _build_guard_detail(resolved_guard.reference, result)
                guard_details.append(detail)
                block_guard_details.append(detail)
                checked_guards.append(resolved_guard.reference)
                if result.status != "ok":
                    block_blockers.append(resolved_guard.reference)
            block_items.append(
                {
                    "block_index": block_index,
                    "type": "guards",
                    "status": "blocked" if block_blockers else "ok",
                    "guard_references": [guard.reference for guard in declared_block.guards],
                    "blockers": block_blockers,
                    "guard_details": block_guard_details,
                }
            )
            if block_blockers:
                skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index + 1))
                return RuntimeResult(
                    mode=Mode.EXECUTE,
                    status=RuntimeStatus.GUARD_FAILED,
                    diagnostics=tuple(diagnostics),
                    plan=check_result.plan,
                    outputs={
                        "can_execute": False,
                        "blockers": block_blockers,
                        "checked_guards": checked_guards,
                        "guard_details": guard_details,
                        "block_items": block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                        "active_profile": active_profile,
                        "active_overrides": [override.to_contract() for override in active_overrides],
                        "executed_steps": executed_steps,
                        "skipped_steps": skipped_steps,
                        "step_condition_details": step_condition_details,
                    },
                    operation_results=tuple(operation_results),
                    failed_guard=block_blockers[0],
                )
            continue

        if isinstance(declared_block, RunBlock):
            assert isinstance(resolved_block, ResolvedRunBlock)
            condition_result = evaluate_run_condition(declared_block, effective_workflow, block_index=block_index)
            if isinstance(condition_result, Diagnostic):
                diagnostics.append(condition_result)
                block_items.append(
                    {
                        "block_index": block_index,
                        "type": "run",
                        "status": "execution_error",
                        "reference": declared_block.run,
                        "failed_run": declared_block.run,
                    }
                )
                skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index + 1))
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
                        "step_condition_details": step_condition_details,
                        "launcher_details": launcher_details,
                        "checked_guards": checked_guards,
                        "guard_details": guard_details,
                        "block_items": block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                    },
                    operation_results=tuple(operation_results),
                    failed_step=declared_block.run,
                )
            if condition_result is False:
                block_items.append(
                    {
                        "block_index": block_index,
                        "type": "run",
                        "status": "skipped",
                        "reference": declared_block.run,
                        "condition": declared_block.if_,
                    }
                )
                continue

            run_workflow = materialize_run_workflow(declared_block, effective_workflow, block_index=block_index)
            if isinstance(run_workflow, Diagnostic):
                diagnostics.append(run_workflow)
                block_items.append(
                    {
                        "block_index": block_index,
                        "type": "run",
                        "status": "execution_error",
                        "reference": declared_block.run,
                        "failed_run": declared_block.run,
                    }
                )
                skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index + 1))
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
                        "step_condition_details": step_condition_details,
                        "launcher_details": launcher_details,
                        "checked_guards": checked_guards,
                        "guard_details": guard_details,
                        "block_items": block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                    },
                    operation_results=tuple(operation_results),
                    failed_step=declared_block.run,
                )

            run_result = execute_workflow(
                run_workflow,
                profile=profile,
                guard_probe=guard_probe,
                step_executor=step_executor,
                connector_provider=connector_provider,
            )
            diagnostics.extend(run_result.diagnostics)
            operation_results.extend(run_result.operation_results)
            executed_steps.extend([name for name in run_result.outputs.get("executed_steps", []) if isinstance(name, str)])
            skipped_steps.extend([name for name in run_result.outputs.get("skipped_steps", []) if isinstance(name, str)])
            step_condition_details.extend([detail for detail in run_result.outputs.get("step_condition_details", []) if isinstance(detail, dict)])
            launcher_details.extend([detail for detail in run_result.outputs.get("launcher_details", []) if isinstance(detail, dict)])
            checked_guards.extend([name for name in run_result.outputs.get("checked_guards", []) if isinstance(name, str)])
            guard_details.extend([detail for detail in run_result.outputs.get("guard_details", []) if isinstance(detail, dict)])
            block_items.append(
                {
                    "block_index": block_index,
                    "type": "run",
                    "status": "ok" if run_result.status is RuntimeStatus.OK else run_result.status.value,
                    "reference": declared_block.run,
                    "nested_block_items": [item for item in run_result.outputs.get("block_items", []) if isinstance(item, dict)],
                }
            )
            if run_result.status is not RuntimeStatus.OK:
                return RuntimeResult(
                    mode=Mode.EXECUTE,
                    status=run_result.status,
                    diagnostics=tuple(diagnostics),
                    plan=check_result.plan,
                    outputs={
                        "can_execute": False,
                        "active_profile": active_profile,
                        "active_overrides": [override.to_contract() for override in active_overrides],
                        "executed_steps": executed_steps,
                        "skipped_steps": skipped_steps,
                        "step_condition_details": step_condition_details,
                        "launcher_details": launcher_details,
                        "checked_guards": checked_guards,
                        "guard_details": guard_details,
                        "block_items": block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                    },
                    operation_results=tuple(operation_results),
                    failed_guard=run_result.failed_guard,
                    failed_step=run_result.failed_step,
                )
            continue

        assert isinstance(declared_block, StepBlock)
        assert isinstance(resolved_block, ResolvedStepBlock)
        block_executed: list[str] = []
        block_skipped: list[str] = []
        for step_index, (step, resolved_step) in enumerate(zip(declared_block.steps, resolved_block.steps, strict=False)):
            if step.if_ is not None:
                condition_result = _evaluate_step_condition(step, effective_workflow)
                if isinstance(condition_result, Diagnostic):
                    step_condition_details.append(
                        {
                            "name": step.name,
                            "condition": step.if_,
                            "outcome": "error",
                            "reason": "condition_evaluation_failed",
                            "result": None,
                            "error_code": condition_result.code,
                        }
                    )
                    skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index, current_step_index=step_index + 1))
                    diagnostics.append(condition_result)
                    block_items.append(
                        {
                            "block_index": block_index,
                            "type": "steps",
                            "status": "execution_error",
                            "step_names": [candidate.name for candidate in declared_block.steps],
                            "executed_steps": block_executed,
                            "skipped_steps": block_skipped + [step.name],
                            "failed_step": step.name,
                        }
                    )
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
                            "step_condition_details": step_condition_details,
                            "launcher_details": launcher_details,
                            "block_items": block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                            "checked_guards": checked_guards,
                            "guard_details": guard_details,
                        },
                        operation_results=tuple(operation_results),
                        failed_step=step.name,
                    )
                if condition_result is False:
                    step_condition_details.append(
                        {
                            "name": step.name,
                            "condition": step.if_,
                            "outcome": "skipped",
                            "reason": "condition_false",
                            "result": False,
                        }
                    )
                    skipped_steps.append(step.name)
                    block_skipped.append(step.name)
                    continue
                step_condition_details.append({"name": step.name, "condition": step.if_, "outcome": "executed", "result": True})
            if isinstance(resolved_step, ResolvedBuiltinStep):
                result = _execute_builtin_step(step, effective_workflow)
            else:
                executed_step = resolved_step
                applied_launcher = None
                if profile is not None:
                    executed_step, applied_launcher, launcher_error = apply_launcher_to_step(step, resolved_step, effective_workflow, profile.launchers)
                    if launcher_error is not None:
                        result = launcher_error
                    else:
                        result = executor(executed_step, effective_workflow)
                else:
                    result = executor(executed_step, effective_workflow)
                if applied_launcher is not None:
                    launcher_details.append(
                        {
                            "step": step.name,
                            "launcher": applied_launcher.name,
                            "connector": applied_launcher.definition.connector,
                            "status": result.status,
                        }
                    )
            if step.register is not None:
                effective_workflow.step_results[step.register] = {
                    "status": result.status,
                    "summary": result.summary,
                    "outputs": dict(result.outputs),
                }
            operation_results.append(result)
            diagnostics.extend(result.diagnostics)

            if result.status != "ok":
                skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index, current_step_index=step_index + 1))
                block_items.append(
                    {
                        "block_index": block_index,
                        "type": "steps",
                        "status": "execution_error",
                        "step_names": [candidate.name for candidate in declared_block.steps],
                        "executed_steps": block_executed,
                        "skipped_steps": block_skipped,
                        "failed_step": step.name,
                    }
                )
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
                        "step_condition_details": step_condition_details,
                        "launcher_details": launcher_details,
                        "block_items": block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                        "checked_guards": checked_guards,
                        "guard_details": guard_details,
                    },
                    operation_results=tuple(operation_results),
                    failed_step=step.name,
                )

            executed_steps.append(step.name)
            block_executed.append(step.name)

        block_items.append(
            {
                "block_index": block_index,
                "type": "steps",
                "status": "ok",
                "step_names": [candidate.name for candidate in declared_block.steps],
                "executed_steps": block_executed,
                "skipped_steps": block_skipped,
            }
        )

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
            "step_condition_details": step_condition_details,
            "launcher_details": launcher_details,
            "checked_guards": checked_guards,
            "guard_details": guard_details,
            "block_items": block_items,
        },
        operation_results=tuple(operation_results),
    )


def _evaluate_step_condition(step, workflow: Workflow) -> bool | Diagnostic:
    try:
        value = resolve_runtime_value(step.if_, workflow, allow_boolean_composition=True)
    except ValueResolutionError as exc:
        return exc.to_diagnostic(path=("steps", step.name, "if"))
    if isinstance(value, bool):
        return value
    return Diagnostic(
        code="runtime.step.if.result_type",
        level="error",
        message="Step condition must evaluate to a boolean value",
        path=("steps", step.name, "if"),
        details={"actual_type": type(value).__name__},
    )


def _default_step_executor(*, provider: ConnectorProvider | None):
    """Default executor backed by canonical connector operations."""

    def execute(resolved_step: ResolvedOperation, workflow: Workflow) -> OperationResult:
        resolved_provider = provider or get_default_connector_provider()
        return resolved_provider.step_executor(resolved_step, workflow)

    return execute


def _execute_builtin_step(step, workflow: Workflow) -> OperationResult:
    try:
        if step.value is not None:
            return _execute_value_step(step.name, step.value, workflow)
        if step.state_set is not None:
            return _execute_state_set(step.name, step.state_set, workflow)
        if step.state_delete is not None:
            return _execute_state_delete(step.name, step.state_delete, workflow)
    except RuntimeStateError as exc:
        return OperationResult(status="state_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))
    except ValueResolutionError as exc:
        return OperationResult(status="state_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))
    return OperationResult(status="state_error", summary="Unknown builtin step form")


def _execute_value_step(step_name: str, raw_value: JSONValue, workflow: Workflow) -> OperationResult:
    value = resolve_runtime_value(raw_value, workflow)
    return OperationResult(
        status="ok",
        summary=f"Materialized derived value for step '{step_name}'",
        outputs={"value": value},
    )


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


def _all_step_names(workflow: Workflow) -> list[str]:
    return [step.name for block in workflow.blocks if isinstance(block, StepBlock) for step in block.steps]


def _initial_checked_block_count(workflow: Workflow) -> int:
    count = 0
    for block in workflow.blocks:
        if isinstance(block, GuardBlock):
            count += 1
            continue
        break
    return count


def _remaining_step_names(workflow: Workflow, *, start_block_index: int, current_step_index: int | None = None) -> list[str]:
    remaining: list[str] = []
    for block_index, block in enumerate(workflow.blocks[start_block_index:], start=start_block_index):
        if not isinstance(block, StepBlock):
            continue
        start_step = current_step_index if block_index == start_block_index and current_step_index is not None else 0
        remaining.extend(step.name for step in block.steps[start_step:])
    return remaining


def _pending_execution_block_items(workflow: Workflow, *, start_block_index: int, blocked: bool) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for block_index, block in enumerate(workflow.blocks[start_block_index:], start=start_block_index):
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
            items.append(
                {
                    "block_index": block_index,
                    "type": "steps",
                    "status": "blocked" if blocked else "pending",
                    "step_names": [step.name for step in block.steps],
                    "executed_steps": [],
                    "skipped_steps": [],
                }
            )
    return items
