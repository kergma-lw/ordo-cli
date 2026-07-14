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
    execution_tree: dict[str, object] | None = None,
) -> RuntimeResult:
    """Execute steps only after validation, resolution, and guards succeed."""

    check_result = check_workflow(
        workflow,
        profile=profile,
        available_profiles=available_profiles,
        guard_probe=guard_probe,
        connector_provider=connector_provider,
    )
    execution_tree_output = dict(execution_tree) if isinstance(execution_tree, dict) else None
    execution_tree_mode, execution_tree_fallback_reason = _execution_tree_compatibility_state(execution_tree_output)
    if check_result.status is not RuntimeStatus.OK:
        return RuntimeResult(
            mode=Mode.EXECUTE,
            status=check_result.status,
            diagnostics=check_result.diagnostics,
            plan=check_result.plan,
            outputs={
                **dict(check_result.outputs),
                "executed_steps": [],
                "reused_steps": [],
                "skipped_steps": _all_step_names(workflow),
                "step_condition_details": [],
                "launcher_details": [],
                "execution_tree": execution_tree_output,
                "execution_tree_mode": execution_tree_mode,
                "execution_tree_fallback_reason": execution_tree_fallback_reason,
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
    reused_steps: list[str] = []
    skipped_steps: list[str] = []
    step_condition_details: list[dict[str, object]] = []
    launcher_details: list[dict[str, object]] = []
    block_items: list[dict[str, object]] = [dict(item) for item in check_result.outputs.get("block_items", []) if isinstance(item, dict)]
    guard_details: list[dict[str, object]] = [dict(item) for item in check_result.outputs.get("guard_details", []) if isinstance(item, dict)]
    checked_guards: list[str] = list(check_result.outputs.get("checked_guards", []))
    preflight_reuse = _build_reusable_preflight_step_map(execution_tree_output)
    effective_workflow.step_results.clear()
    for reused_result in preflight_reuse.values():
        register = reused_result.get("register")
        if isinstance(register, str):
            effective_workflow.step_results[register] = reused_result["step_result"]
    _prime_execution_tree_with_checked_guards(execution_tree_output, guard_details)

    start_block_index = _execution_start_block_index(effective_workflow, execution_tree_output)
    for step_name in list(preflight_reuse):
        block_index = _execution_tree_step_block_index(execution_tree_output, step_name)
        if block_index is not None and block_index < start_block_index:
            reused_steps.append(step_name)
            _mark_execution_tree_step_reused(execution_tree_output, step_name)

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
                _mark_execution_tree_guard_runtime(execution_tree_output, resolved_guard.reference, result)
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
                    outputs=_build_execute_outputs(
                        can_execute=False,
                        active_profile=active_profile,
                        active_overrides=active_overrides,
                        execution_tree=execution_tree_output,
                        execution_tree_mode=execution_tree_mode,
                        execution_tree_fallback_reason=execution_tree_fallback_reason,
                        executed_steps=executed_steps,
                        reused_steps=reused_steps,
                        skipped_steps=skipped_steps,
                        step_condition_details=step_condition_details,
                        launcher_details=launcher_details,
                        checked_guards=checked_guards,
                        guard_details=guard_details,
                        block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                        extra={"blockers": block_blockers},
                    ),
                    operation_results=tuple(operation_results),
                    failed_guard=block_blockers[0],
                )
            continue

        assert isinstance(declared_block, StepBlock)
        assert isinstance(resolved_block, ResolvedStepBlock)
        block_executed: list[str] = []
        block_skipped: list[str] = []
        for step_index, (step, resolved_step) in enumerate(zip(declared_block.steps, resolved_block.steps, strict=False)):
            if not _should_execute_step_from_tree(execution_tree_output, block_index=block_index, step_index=step_index, step_name=step.name):
                continue
            reused_preflight = preflight_reuse.get(step.name)
            condition_source = _condition_source_from_tree_state(step, effective_workflow, execution_tree_output)
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
                            "source": condition_source,
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
                        outputs=_build_execute_outputs(
                            can_execute=False,
                            active_profile=active_profile,
                            active_overrides=active_overrides,
                            execution_tree=execution_tree_output,
                            execution_tree_mode=execution_tree_mode,
                            execution_tree_fallback_reason=execution_tree_fallback_reason,
                            executed_steps=executed_steps,
                            reused_steps=reused_steps,
                            skipped_steps=skipped_steps,
                            step_condition_details=step_condition_details,
                            launcher_details=launcher_details,
                            checked_guards=checked_guards,
                            guard_details=guard_details,
                            block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                        ),
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
                            "source": condition_source,
                        }
                    )
                    skipped_steps.append(step.name)
                    block_skipped.append(step.name)
                    _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="skipped_at_run")
                    continue
                step_condition_details.append({"name": step.name, "condition": step.if_, "outcome": "executed", "result": True, "source": condition_source})
            if reused_preflight is not None:
                reused_steps.append(step.name)
                block_executed.append(step.name)
                _mark_execution_tree_step_reused(execution_tree_output, step.name)
                continue
            if execution_tree_output is not None and isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "probe":
                with _execution_working_directory(current_working_directory):
                    result = (guard_probe or _default_guard_probe(provider=connector_provider))(resolved_step, effective_workflow)
                if step.register is not None:
                    effective_workflow.step_results[step.register] = {
                        "status": result.status,
                        "summary": result.summary,
                        "outputs": dict(result.outputs),
                    }
                operation_results.append(result)
                diagnostics.extend(result.diagnostics)
                _mark_execution_tree_probe_revalidated(execution_tree_output, step.name, result)
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
                        outputs=_build_execute_outputs(
                            can_execute=False,
                            active_profile=active_profile,
                            active_overrides=active_overrides,
                            execution_tree=execution_tree_output,
                            execution_tree_mode=execution_tree_mode,
                            execution_tree_fallback_reason=execution_tree_fallback_reason,
                            executed_steps=executed_steps,
                            reused_steps=reused_steps,
                            skipped_steps=skipped_steps,
                            step_condition_details=step_condition_details,
                            launcher_details=launcher_details,
                            checked_guards=checked_guards,
                            guard_details=guard_details,
                            block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                        ),
                        operation_results=tuple(operation_results),
                        failed_step=step.name,
                    )
                executed_steps.append(step.name)
                block_executed.append(step.name)
                continue
            if isinstance(resolved_step, ResolvedRunStep):
                run_workflow = materialize_run_workflow(step, effective_workflow, block_index=block_index, step_index=step_index)
                if isinstance(run_workflow, Diagnostic):
                    _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="failed")
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
                        outputs=_build_execute_outputs(
                            can_execute=False,
                            active_profile=active_profile,
                            active_overrides=active_overrides,
                            execution_tree=execution_tree_output,
                            execution_tree_mode=execution_tree_mode,
                            execution_tree_fallback_reason=execution_tree_fallback_reason,
                            executed_steps=executed_steps,
                            reused_steps=reused_steps,
                            skipped_steps=skipped_steps,
                            step_condition_details=step_condition_details,
                            launcher_details=launcher_details,
                            checked_guards=checked_guards,
                            guard_details=guard_details,
                            block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                        ),
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
                    _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="failed")
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
                        outputs=_build_execute_outputs(
                            can_execute=False,
                            active_profile=active_profile,
                            active_overrides=active_overrides,
                            execution_tree=execution_tree_output,
                            execution_tree_mode=execution_tree_mode,
                            execution_tree_fallback_reason=execution_tree_fallback_reason,
                            executed_steps=executed_steps,
                            reused_steps=reused_steps,
                            skipped_steps=skipped_steps,
                            step_condition_details=step_condition_details,
                            launcher_details=launcher_details,
                            checked_guards=checked_guards,
                            guard_details=guard_details,
                            block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                        ),
                        operation_results=tuple(operation_results),
                        failed_guard=run_result.failed_guard,
                        failed_step=run_result.failed_step or step.name,
                    )
                _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="done")
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
                        _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="failed")
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
                            outputs=_build_execute_outputs(
                                can_execute=False,
                                active_profile=active_profile,
                                active_overrides=active_overrides,
                                execution_tree=execution_tree_output,
                                execution_tree_mode=execution_tree_mode,
                                execution_tree_fallback_reason=execution_tree_fallback_reason,
                                executed_steps=executed_steps,
                                reused_steps=reused_steps,
                                skipped_steps=skipped_steps,
                                step_condition_details=step_condition_details,
                                launcher_details=launcher_details,
                                checked_guards=checked_guards,
                                guard_details=guard_details,
                                block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                            ),
                            operation_results=tuple(operation_results),
                            failed_step=step.name,
                        )
                    executed_steps.append(step.name)
                    block_executed.append(step.name)
                    _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="done", result=result)
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
                        _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="failed")
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
                            outputs=_build_execute_outputs(
                                can_execute=False,
                                active_profile=active_profile,
                                active_overrides=active_overrides,
                                execution_tree=execution_tree_output,
                                execution_tree_mode=execution_tree_mode,
                                execution_tree_fallback_reason=execution_tree_fallback_reason,
                                executed_steps=executed_steps,
                                reused_steps=reused_steps,
                                skipped_steps=skipped_steps,
                                step_condition_details=step_condition_details,
                                launcher_details=launcher_details,
                                checked_guards=checked_guards,
                                guard_details=guard_details,
                                block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                            ),
                            operation_results=tuple(operation_results),
                            failed_step=step.name,
                        )
                    executed_steps.append(step.name)
                    block_executed.append(step.name)
                    _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="done", result=result)
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
                _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="failed")
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
                    outputs=_build_execute_outputs(
                        can_execute=False,
                        active_profile=active_profile,
                        active_overrides=active_overrides,
                        execution_tree=execution_tree_output,
                        execution_tree_mode=execution_tree_mode,
                        execution_tree_fallback_reason=execution_tree_fallback_reason,
                        executed_steps=executed_steps,
                        reused_steps=reused_steps,
                        skipped_steps=skipped_steps,
                        step_condition_details=step_condition_details,
                        launcher_details=launcher_details,
                        checked_guards=checked_guards,
                        guard_details=guard_details,
                        block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                    ),
                    operation_results=tuple(operation_results),
                    failed_step=step.name,
                )

            executed_steps.append(step.name)
            block_executed.append(step.name)
            _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="done", result=result)

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
        outputs=_build_execute_outputs(
            can_execute=True,
            active_profile=active_profile,
            active_overrides=active_overrides,
            execution_tree=execution_tree_output,
            execution_tree_mode=execution_tree_mode,
            execution_tree_fallback_reason=execution_tree_fallback_reason,
            executed_steps=executed_steps,
            reused_steps=reused_steps,
            skipped_steps=skipped_steps,
            step_condition_details=step_condition_details,
            launcher_details=launcher_details,
            checked_guards=checked_guards,
            guard_details=guard_details,
            block_items=block_items,
        ),
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


def _build_reusable_preflight_step_map(execution_tree: dict[str, object] | None) -> dict[str, dict[str, object]]:
    if not isinstance(execution_tree, dict):
        return {}
    reusable: dict[str, dict[str, object]] = {}
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for child in block.get("children", []):
            if not isinstance(child, dict):
                continue
            preflight = child.get("preflight")
            if not isinstance(preflight, dict):
                continue
            if child.get("reuse_policy") != "reusable" or preflight.get("status") != "interpreted":
                continue
            register = preflight.get("register")
            outputs = preflight.get("outputs")
            if not isinstance(register, str) or not isinstance(outputs, dict):
                continue
            reusable_name = child.get("name")
            if isinstance(reusable_name, str):
                reusable[reusable_name] = {
                    "register": register,
                    "step_result": {
                        "status": preflight.get("operation_status", "ok"),
                        "summary": preflight.get("summary", "Reused preflight result"),
                        "outputs": dict(outputs),
                    },
                }
    return reusable


def _mark_execution_tree_step_reused(execution_tree: dict[str, object] | None, step_name: str) -> None:
    if not isinstance(execution_tree, dict):
        return
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for child in block.get("children", []):
            if not isinstance(child, dict) or child.get("name") != step_name:
                continue
            child["runtime_status"] = "reused_preflight"
            child["revalidated"] = False
            child["runtime_observation"] = child.get("planned_observation")
            child["divergence_status"] = "matched"
            child["divergence_reason"] = None
            _refresh_execution_tree_block_runtime(block)
            return


def _mark_execution_tree_step_runtime(
    execution_tree: dict[str, object] | None,
    step_name: str,
    *,
    runtime_status: str,
    result: OperationResult | None = None,
) -> None:
    if not isinstance(execution_tree, dict):
        return
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for child in block.get("children", []):
            if not isinstance(child, dict) or child.get("name") != step_name:
                continue
            if result is not None:
                runtime = dict(result.outputs)
                child["runtime_observation"] = runtime
                planned = child.get("planned_observation")
                child["divergence_status"] = "matched" if planned in (None, runtime) else "diverged"
                child["divergence_reason"] = None if planned in (None, runtime) else "runtime_observation_mismatch"
            child["runtime_status"] = runtime_status
            _refresh_execution_tree_block_runtime(block)
            return


def _mark_execution_tree_guard_runtime(execution_tree: dict[str, object] | None, guard_reference: str, result: OperationResult) -> None:
    if not isinstance(execution_tree, dict):
        return
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for child in block.get("children", []):
            if not isinstance(child, dict) or child.get("reference") != guard_reference:
                continue
            child["runtime_status"] = "done" if result.status == "ok" else "failed"
            child["runtime_observation"] = dict(result.outputs)
            child["divergence_status"] = "matched"
            child["divergence_reason"] = None
            _refresh_execution_tree_block_runtime(block)
            return


def _mark_execution_tree_probe_revalidated(execution_tree: dict[str, object] | None, step_name: str, result: OperationResult) -> None:
    if not isinstance(execution_tree, dict):
        return
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for child in block.get("children", []):
            if not isinstance(child, dict) or child.get("name") != step_name:
                continue
            planned = child.get("planned_observation")
            runtime = dict(result.outputs)
            child["runtime_status"] = "revalidated"
            child["revalidated"] = True
            child["runtime_observation"] = runtime
            child["divergence_status"] = "matched" if planned == runtime else "diverged"
            child["divergence_reason"] = None if planned == runtime else "runtime_observation_mismatch"
            _refresh_execution_tree_block_runtime(block)
            return


def _condition_source_from_tree_state(step: Step, workflow: Workflow, execution_tree: dict[str, object] | None) -> str:
    if step.if_ is None or not isinstance(execution_tree, dict):
        return "runtime"
    if "step." not in step.if_:
        return "runtime"
    return "execution_tree_state" if bool(workflow.step_results) else "runtime"


def _refresh_execution_tree_block_runtime(block: dict[str, object]) -> None:
    statuses = {
        child.get("runtime_status")
        for child in block.get("children", [])
        if isinstance(child, dict) and isinstance(child.get("runtime_status"), str)
    }
    if not statuses or statuses == {"not_started"}:
        block["runtime_status"] = "not_started"
        return
    if "failed" in statuses:
        block["runtime_status"] = "failed"
        return
    if statuses.issubset({"done", "reused_preflight", "skipped_at_run"}):
        block["runtime_status"] = "done"
        return
    block["runtime_status"] = "in_progress"


def _prime_execution_tree_with_checked_guards(execution_tree: dict[str, object] | None, guard_details: list[dict[str, object]]) -> None:
    if not isinstance(execution_tree, dict):
        return
    detail_by_reference = {
        detail.get("reference"): detail
        for detail in guard_details
        if isinstance(detail, dict) and isinstance(detail.get("reference"), str)
    }
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for child in block.get("children", []):
            if not isinstance(child, dict):
                continue
            reference = child.get("reference")
            if not isinstance(reference, str) or reference not in detail_by_reference:
                continue
            detail = detail_by_reference[reference]
            child["runtime_status"] = "done" if detail.get("status") == "ok" else "failed"
            _refresh_execution_tree_block_runtime(block)


def _initial_checked_block_count(workflow: Workflow) -> int:
    count = 0
    for block in workflow.blocks:
        if isinstance(block, GuardBlock):
            count += 1
            continue
        break
    return count


def _execution_start_block_index(workflow: Workflow, execution_tree: dict[str, object] | None) -> int:
    if isinstance(execution_tree, dict):
        return _frontier_start_block_index(execution_tree)
    return _initial_checked_block_count(workflow)


def _frontier_start_block_index(execution_tree: dict[str, object] | None) -> int:
    if not isinstance(execution_tree, dict):
        return 0
    frontier = execution_tree.get("ready_to_run_frontier")
    if not isinstance(frontier, dict):
        return 0
    required = [node_id for node_id in frontier.get("requires_runtime_node_ids", []) if isinstance(node_id, str)]
    block_indexes: list[int] = []
    for node_id in required:
        parts = node_id.split(":")
        if len(parts) < 2 or parts[0] != "block":
            continue
        try:
            block_indexes.append(int(parts[1]))
        except ValueError:
            continue
    return 0 if not block_indexes else min(block_indexes)


def _execution_tree_step_block_index(execution_tree: dict[str, object] | None, step_name: str) -> int | None:
    if not isinstance(execution_tree, dict):
        return None
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        block_index = block.get("block_index")
        if not isinstance(block_index, int):
            continue
        for child in block.get("children", []):
            if isinstance(child, dict) and child.get("name") == step_name:
                return block_index
    return None


def _required_runtime_node_ids(execution_tree: dict[str, object] | None) -> set[str]:
    if not isinstance(execution_tree, dict):
        return set()
    frontier = execution_tree.get("ready_to_run_frontier")
    if not isinstance(frontier, dict):
        return set()
    return {node_id for node_id in frontier.get("requires_runtime_node_ids", []) if isinstance(node_id, str)}


def _should_execute_step_from_tree(
    execution_tree: dict[str, object] | None,
    *,
    block_index: int,
    step_index: int,
    step_name: str,
) -> bool:
    if not isinstance(execution_tree, dict):
        return True
    node_id = f"block:{block_index}:step:{step_index}"
    required = _required_runtime_node_ids(execution_tree)
    if required:
        return node_id in required
    runtime_status = _execution_tree_step_runtime_status(execution_tree, step_name)
    return runtime_status == "not_started"


def _execution_tree_step_runtime_status(execution_tree: dict[str, object] | None, step_name: str) -> str | None:
    if not isinstance(execution_tree, dict):
        return None
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for child in block.get("children", []):
            if isinstance(child, dict) and child.get("name") == step_name and isinstance(child.get("runtime_status"), str):
                return child["runtime_status"]
    return None


def _remaining_step_names(workflow: Workflow, *, start_block_index: int, current_step_index: int | None = None) -> list[str]:
    remaining: list[str] = []
    for block_index, block in enumerate(workflow.blocks[start_block_index:], start=start_block_index):
        if not isinstance(block, StepBlock):
            continue
        start_step = current_step_index if block_index == start_block_index and current_step_index is not None else 0
        remaining.extend(step.name for step in block.steps[start_step:])
    return remaining


def _execution_step_summaries_from_tree(
    execution_tree: dict[str, object] | None,
    *,
    executed_steps: list[str],
    reused_steps: list[str],
    skipped_steps: list[str],
) -> dict[str, list[str]]:
    if not isinstance(execution_tree, dict):
        return {
            "executed_steps": executed_steps,
            "reused_steps": reused_steps,
            "skipped_steps": skipped_steps,
        }
    derived_executed: list[str] = []
    derived_reused: list[str] = []
    derived_skipped: list[str] = []
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for child in block.get("children", []):
            if not isinstance(child, dict):
                continue
            step_name = child.get("name")
            if not isinstance(step_name, str):
                continue
            runtime_status = child.get("runtime_status")
            if runtime_status == "reused_preflight":
                derived_reused.append(step_name)
            elif runtime_status == "done":
                derived_executed.append(step_name)
            elif runtime_status == "skipped_at_run":
                derived_skipped.append(step_name)
    return {
        "executed_steps": derived_executed or executed_steps,
        "reused_steps": derived_reused or reused_steps,
        "skipped_steps": derived_skipped or skipped_steps,
    }


def _execution_tree_compatibility_state(execution_tree: dict[str, object] | None) -> tuple[str, str | None]:
    if not isinstance(execution_tree, dict):
        return ("legacy_fallback", "missing_execution_tree")
    frontier = execution_tree.get("ready_to_run_frontier")
    if not isinstance(frontier, dict):
        return ("legacy_fallback", "missing_frontier")
    return ("tree_assisted", None)


def _build_execute_outputs(
    *,
    can_execute: bool,
    active_profile: str | None,
    active_overrides,
    execution_tree: dict[str, object] | None,
    execution_tree_mode: str,
    execution_tree_fallback_reason: str | None,
    executed_steps: list[str],
    reused_steps: list[str],
    skipped_steps: list[str],
    step_condition_details: list[dict[str, object]],
    launcher_details: list[dict[str, object]],
    checked_guards: list[str],
    guard_details: list[dict[str, object]],
    block_items: list[dict[str, object]],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    outputs = {
        "can_execute": can_execute,
        "active_profile": active_profile,
        "active_overrides": [override.to_contract() for override in active_overrides],
        **_execution_step_summaries_from_tree(execution_tree, executed_steps=executed_steps, reused_steps=reused_steps, skipped_steps=skipped_steps),
        "step_condition_details": step_condition_details,
        "launcher_details": launcher_details,
        "checked_guards": checked_guards,
        "guard_details": guard_details,
        "block_items": block_items,
        "execution_tree": execution_tree,
        "execution_tree_mode": execution_tree_mode,
        "execution_tree_fallback_reason": execution_tree_fallback_reason,
    }
    if extra:
        outputs.update(extra)
    return outputs


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
