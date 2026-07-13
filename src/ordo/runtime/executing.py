"""Minimal contract-first execute mode."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import GuardBlock, Step, StepBlock, Workflow

from .checking import GuardProbe, _build_guard_detail, _default_guard_probe, _evaluate_guard_expression, check_workflow
from .fragment_runs import evaluate_run_condition, materialize_run_workflow
from .launchers import apply_launcher_to_step
from .preflight_interpreter import evaluate_preflight_step_condition, evaluate_preflight_value_step
from .profiles import apply_profile_defaults_to_subsequent_steps, apply_profile_to_workflow
from .providers import ConnectorProvider, StepExecutor, get_default_connector_provider
from .resolution import ResolvedBuiltinStep, ResolvedGuardBlock, ResolvedGuardExpression, ResolvedOperation, ResolvedRunStep, ResolvedStepBlock, resolve_workflow_references
from .state import RuntimeStateError, delete_state_value, read_state_document, resolve_state_target, write_state_document, write_state_value
from .value_resolution import ValueResolutionError, resolve_runtime_value


def execute_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    available_profiles: dict[str, Profile] | None = None,
    profile_working_directories: dict[str, Path | None] | None = None,
    guard_probe: GuardProbe | None = None,
    step_executor: StepExecutor | None = None,
    connector_provider: ConnectorProvider | None = None,
) -> RuntimeResult:
    """Execute steps only after validation, resolution, and guards succeed."""

    check_result = check_workflow(
        workflow,
        profile=profile,
        available_profiles=available_profiles,
        guard_probe=guard_probe,
        connector_provider=connector_provider,
    )
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

    current_profile = profile
    current_profile_name = None if profile is None else profile.name
    current_working_directory = None if current_profile_name is None or profile_working_directories is None else profile_working_directories.get(current_profile_name)

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
                    with _execution_working_directory(current_working_directory):
                        result = _evaluate_guard_expression(resolved_guard, effective_workflow, guard_probe or _default_guard_probe(provider=connector_provider))
                else:
                    with _execution_working_directory(current_working_directory):
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
            if isinstance(resolved_step, ResolvedRunStep):
                run_workflow = materialize_run_workflow(step, effective_workflow, block_index=block_index, step_index=step_index)
                if isinstance(run_workflow, Diagnostic):
                    skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index, current_step_index=step_index + 1))
                    diagnostics.append(run_workflow)
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
                            "checked_guards": checked_guards,
                            "guard_details": guard_details,
                            "block_items": block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                        },
                        operation_results=tuple(operation_results),
                        failed_step=step.name,
                    )

                run_result = execute_workflow(
                    run_workflow,
                    profile=current_profile,
                    available_profiles=available_profiles,
                    profile_working_directories=profile_working_directories,
                    guard_probe=guard_probe,
                    step_executor=step_executor,
                    connector_provider=connector_provider,
                )
                diagnostics.extend(run_result.diagnostics)
                operation_results.extend(run_result.operation_results)
                propagated_profile = run_result.outputs.get("active_profile")
                if isinstance(propagated_profile, str) and available_profiles is not None and propagated_profile in available_profiles:
                    current_profile = available_profiles[propagated_profile]
                    current_profile_name = propagated_profile
                    current_working_directory = None if profile_working_directories is None else profile_working_directories.get(propagated_profile)
                    active_profile = propagated_profile
                    active_overrides = current_profile.overrides
                executed_steps.append(step.name)
                block_executed.append(step.name)
                executed_steps.extend([name for name in run_result.outputs.get("executed_steps", []) if isinstance(name, str)])
                skipped_steps.extend([name for name in run_result.outputs.get("skipped_steps", []) if isinstance(name, str)])
                step_condition_details.extend([detail for detail in run_result.outputs.get("step_condition_details", []) if isinstance(detail, dict)])
                launcher_details.extend([detail for detail in run_result.outputs.get("launcher_details", []) if isinstance(detail, dict)])
                checked_guards.extend([name for name in run_result.outputs.get("checked_guards", []) if isinstance(name, str)])
                guard_details.extend([detail for detail in run_result.outputs.get("guard_details", []) if isinstance(detail, dict)])
                if run_result.status is not RuntimeStatus.OK:
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
                            "failed_run": step.run,
                        }
                    )
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
                        failed_step=run_result.failed_step or step.name,
                    )
                continue
            if isinstance(resolved_step, ResolvedBuiltinStep):
                if resolved_step.builtin == "profile_switch":
                    result, current_profile, current_profile_name, active_profile, active_overrides, current_working_directory, effective_workflow = _execute_profile_switch_step(
                        step,
                        effective_workflow,
                        current_profile=current_profile,
                        available_profiles=available_profiles,
                        profile_working_directories=profile_working_directories,
                    )
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
                                "checked_guards": checked_guards,
                                "guard_details": guard_details,
                                "block_items": block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                            },
                            operation_results=tuple(operation_results),
                            failed_step=step.name,
                        )
                    executed_steps.append(step.name)
                    block_executed.append(step.name)
                    continue
                with _execution_working_directory(current_working_directory):
                    result = _execute_builtin_step(step, effective_workflow)
            else:
                if resolved_step.reference == "runtime.profile.use":
                    result, current_profile, current_profile_name, active_profile, active_overrides, current_working_directory, effective_workflow = _execute_profile_switch_step(
                        step,
                        effective_workflow,
                        current_profile=current_profile,
                        available_profiles=available_profiles,
                        profile_working_directories=profile_working_directories,
                    )
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
                    continue
                executed_step = resolved_step
                applied_launcher = None
                if current_profile is not None:
                    executed_step, applied_launcher, launcher_error = apply_launcher_to_step(step, resolved_step, effective_workflow, current_profile.launchers)
                    if launcher_error is not None:
                        result = launcher_error
                    else:
                        with _execution_working_directory(current_working_directory):
                            result = executor(executed_step, effective_workflow)
                else:
                    with _execution_working_directory(current_working_directory):
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
    value = evaluate_preflight_step_condition(step, workflow)
    if isinstance(value, bool):
        return value
    if isinstance(value, ValueResolutionError):
        return value.to_diagnostic(path=("steps", step.name, "if"))
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


def _execute_profile_switch_step(
    step: Step,
    workflow: Workflow,
    *,
    current_profile: Profile | None,
    available_profiles: dict[str, Profile] | None,
    profile_working_directories: dict[str, Path | None] | None,
) -> tuple[OperationResult, Profile | None, str | None, str | None, tuple, Path | None, Workflow]:
    raw_profile = step.profile_switch
    if raw_profile is None:
        declared_inputs = {} if step.operation is None else step.operation.with_
        raw_profile = declared_inputs.get("profile")
    if raw_profile is None:
        return (
            OperationResult(status="input_error", summary="Required input 'profile' is missing"),
            current_profile,
            None if current_profile is None else current_profile.name,
            None if current_profile is None else current_profile.name,
            () if current_profile is None else current_profile.overrides,
            None if current_profile is None or profile_working_directories is None else profile_working_directories.get(current_profile.name),
            workflow,
        )
    try:
        profile_name = resolve_runtime_value(raw_profile, workflow)
    except ValueResolutionError as exc:
        return (
            OperationResult(status="input_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),)),
            current_profile,
            None if current_profile is None else current_profile.name,
            None if current_profile is None else current_profile.name,
            () if current_profile is None else current_profile.overrides,
            None if current_profile is None or profile_working_directories is None else profile_working_directories.get(current_profile.name),
            workflow,
        )
    if not isinstance(profile_name, str) or not profile_name:
        return (
            OperationResult(status="input_error", summary="Runtime profile switch requires a non-empty string profile name"),
            current_profile,
            None if current_profile is None else current_profile.name,
            None if current_profile is None else current_profile.name,
            () if current_profile is None else current_profile.overrides,
            None if current_profile is None or profile_working_directories is None else profile_working_directories.get(current_profile.name),
            workflow,
        )
    if available_profiles is None or profile_name not in available_profiles:
        return (
            OperationResult(status="execution_error", summary=f"Runtime profile '{profile_name}' is not available in this execution context"),
            current_profile,
            None if current_profile is None else current_profile.name,
            None if current_profile is None else current_profile.name,
            () if current_profile is None else current_profile.overrides,
            None if current_profile is None or profile_working_directories is None else profile_working_directories.get(current_profile.name),
            workflow,
        )
    target_profile = available_profiles[profile_name]
    target_working_directory = None if profile_working_directories is None else profile_working_directories.get(profile_name)
    previous = None if current_profile is None else current_profile.name
    applied = apply_profile_defaults_to_subsequent_steps(workflow, target_profile)
    switched_workflow = workflow if applied.workflow is None else applied.workflow
    return (
        OperationResult(
            status="ok",
            summary="Runtime profile switched",
            outputs={
                "profile": profile_name,
                "previous_profile": previous,
                "changed": previous != profile_name,
                "applied_inputs": dict(switched_workflow.inputs),
            },
        ),
        target_profile,
        profile_name,
        profile_name,
        target_profile.overrides,
        target_working_directory,
        switched_workflow,
    )


@contextlib.contextmanager
def _execution_working_directory(target: Path | None):
    if target is None:
        yield
        return
    previous = Path.cwd()
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(previous)


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
    return evaluate_preflight_value_step(Step(name=step_name, value=raw_value), workflow)


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
