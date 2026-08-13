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

from .checking import GuardProbe, _build_guard_detail, _build_preflight_observation_session, _default_guard_probe, _evaluate_guard_expression, check_workflow
from .conditions import ConditionEvaluationReport, summarize_failed_condition_causes, summarize_unknown_condition_causes
from .conditions import ConditionShapeError, iter_condition_expression_leaves, normalize_condition_authoring
from .fragment_runs import evaluate_run_condition, materialize_run_workflow
from .gate_failure_context import evaluate_gate_failure_context
from .launchers import apply_launcher_to_step
from .local_expression_contexts import LocalExpressionContext
from .local_expressions import evaluate_condition_report
from .preflight_interpreter import evaluate_preflight_step_condition, evaluate_preflight_value_step
from .profiles import apply_profile_defaults_to_subsequent_steps, apply_profile_to_workflow, apply_runtime_profile_switch
from .providers import ConnectorProvider, StepExecutor, get_default_connector_provider
from .resolution import ResolvedBuiltinStep, ResolvedConditionExpression, ResolvedGuardBlock, ResolvedOperation, ResolvedRunStep, ResolvedStepBlock, resolve_workflow_references
from .routines import execute_routine_step
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
    invoked_by_run: bool = False,
    invoked_run_reference: str | None = None,
) -> RuntimeResult:
    """Execute steps only after validation, resolution, and guards succeed."""

    check_result = check_workflow(
        workflow,
        profile=profile,
        available_profiles=available_profiles,
        profile_working_directories=profile_working_directories,
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
                **_build_execute_outputs(
                    can_execute=False,
                    active_profile=None,
                    active_overrides=(),
                    execution_tree=execution_tree_output,
                    execution_tree_mode=execution_tree_mode,
                    execution_tree_fallback_reason=execution_tree_fallback_reason,
                    executed_steps=[],
                    reused_steps=[],
                    skipped_steps=_all_step_names(workflow),
                    step_condition_details=[],
                    step_gate_details=[],
                    launcher_details=[],
                    checked_guards=list(check_result.outputs.get("checked_guards", [])),
                    guard_details=[dict(item) for item in check_result.outputs.get("guard_details", []) if isinstance(item, dict)],
                    block_items=[dict(item) for item in check_result.outputs.get("block_items", []) if isinstance(item, dict)],
                ),
            },
            operation_results=check_result.operation_results,
            failed_guard=check_result.failed_guard,
            failed_step=check_result.failed_step,
        )

    context = _initialize_execute_context(
        workflow,
        profile=profile,
        available_profiles=available_profiles,
        profile_working_directories=profile_working_directories,
    )
    effective_workflow = context["workflow"]
    active_profile = context["active_profile"]
    active_overrides = context["active_overrides"]
    current_profile = context["current_profile"]
    current_profile_name = context["current_profile_name"]
    current_working_directory = context["current_working_directory"]

    resolution = resolve_workflow_references(effective_workflow, connector_provider=connector_provider, active_overrides=active_overrides)
    executor = step_executor or _default_step_executor(provider=connector_provider)
    resolved_guard_probe = guard_probe or _default_guard_probe(provider=connector_provider)
    observation_session = _build_preflight_observation_session(
        effective_workflow,
        probe=resolved_guard_probe,
        connector_provider=connector_provider,
    )
    diagnostics: list[Diagnostic] = list(check_result.diagnostics)
    operation_results: list[OperationResult] = list(check_result.operation_results)
    executed_steps: list[str] = []
    reused_steps: list[str] = []
    skipped_steps: list[str] = []
    workflow_results: list[JSONValue] = []
    published_results: list[JSONValue] = []
    step_condition_details: list[dict[str, object]] = []
    step_gate_details: list[dict[str, object]] = []
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
                if isinstance(resolved_guard, ResolvedConditionExpression):
                    with _execution_working_directory(current_working_directory):
                        result = _evaluate_guard_expression(resolved_guard, effective_workflow, resolved_guard_probe)
                else:
                    with _execution_working_directory(current_working_directory):
                        result = resolved_guard_probe(resolved_guard, effective_workflow)
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
                        step_gate_details=step_gate_details,
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
            step_context = _prepare_tree_driven_step_context(
                step=step,
                workflow=effective_workflow,
                execution_tree=execution_tree_output,
                preflight_reuse=preflight_reuse,
                block_index=block_index,
                step_index=step_index,
            )
            if not step_context["should_execute"]:
                continue
            reused_preflight = step_context["reused_preflight"]
            condition_source = step_context["condition_source"]
            if step.if_ is not None:
                condition_result = _evaluate_step_condition(step, effective_workflow, observation_session=observation_session)
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
                    _append_execution_error_block_item(
                        block_items,
                        block_index=block_index,
                        declared_block=declared_block,
                        executed_steps=block_executed,
                        skipped_steps=block_skipped + [step.name],
                        failed_step=step.name,
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
                            step_gate_details=step_gate_details,
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
            gate_report = _evaluate_step_gate(step, effective_workflow, observation_session=observation_session)
            if gate_report is not None:
                step_gate_details.append(
                    _gate_detail(
                        step,
                        gate_report,
                        source=condition_source,
                        workflow=effective_workflow,
                        step_results=effective_workflow.step_results,
                    )
                )
                if gate_report.verdict != "passed":
                    skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index, current_step_index=step_index + 1))
                    diagnostics.append(
                        _gate_failure_diagnostic(
                            step,
                            gate_report,
                            workflow=effective_workflow,
                            step_results=effective_workflow.step_results,
                        )
                    )
                    _append_execution_error_block_item(
                        block_items,
                        block_index=block_index,
                        declared_block=declared_block,
                        executed_steps=block_executed,
                        skipped_steps=block_skipped,
                        failed_step=step.name,
                    )
                    _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="gate_blocked")
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
                            step_gate_details=step_gate_details,
                            launcher_details=launcher_details,
                            checked_guards=checked_guards,
                            guard_details=guard_details,
                            block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                            extra={"gate_blockers": [step.name]},
                        ),
                        operation_results=tuple(operation_results),
                        failed_step=step.name,
                    )
            if reused_preflight is not None:
                reused_steps.append(step.name)
                block_executed.append(step.name)
                _mark_execution_tree_step_reused(execution_tree_output, step.name)
                continue
            if _is_execute_probe_step(execution_tree_output, resolved_step):
                with _execution_working_directory(current_working_directory):
                    result = resolved_guard_probe(resolved_step, effective_workflow)
                if step.register is not None:
                    pass
                _record_step_runtime_result(
                    workflow=effective_workflow,
                    step=step,
                    result=result,
                    operation_results=operation_results,
                    diagnostics=diagnostics,
                )
                _mark_execution_tree_probe_revalidated(execution_tree_output, step.name, result)
                if result.status != "ok":
                    skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index, current_step_index=step_index + 1))
                    _append_execution_error_block_item(
                        block_items,
                        block_index=block_index,
                        declared_block=declared_block,
                        executed_steps=block_executed,
                        skipped_steps=block_skipped,
                        failed_step=step.name,
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
                            step_gate_details=step_gate_details,
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
            if _is_execute_run_step(resolved_step):
                if step.for_each is None:
                    run_workflow = materialize_run_workflow(step, effective_workflow, block_index=block_index, step_index=step_index)
                else:
                    run_workflow = None
                if isinstance(run_workflow, Diagnostic):
                    _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="failed")
                    skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index, current_step_index=step_index + 1))
                    diagnostics.append(run_workflow)
                    _append_execution_error_block_item(
                        block_items,
                        block_index=block_index,
                        declared_block=declared_block,
                        executed_steps=block_executed,
                        skipped_steps=block_skipped,
                        failed_step=step.name,
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
                            step_gate_details=step_gate_details,
                            launcher_details=launcher_details,
                            checked_guards=checked_guards,
                            guard_details=guard_details,
                            block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                        ),
                        operation_results=tuple(operation_results),
                        failed_step=step.name,
                    )

                fan_out_items = _evaluate_run_for_each_items(
                    step,
                    effective_workflow,
                    block_index=block_index,
                    step_index=step_index,
                    observation_session=observation_session,
                )
                if isinstance(fan_out_items, Diagnostic):
                    diagnostics.append(fan_out_items)
                    _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="failed")
                    skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index, current_step_index=step_index + 1))
                    _append_execution_error_block_item(
                        block_items,
                        block_index=block_index,
                        declared_block=declared_block,
                        executed_steps=block_executed,
                        skipped_steps=block_skipped,
                        failed_step=step.name,
                        failed_run=step.run,
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
                            step_gate_details=step_gate_details,
                            launcher_details=launcher_details,
                            checked_guards=checked_guards,
                            guard_details=guard_details,
                            block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                            extra={"fan_out_failure": {"step": step.name, "phase": "before_expansion"}},
                        ),
                        operation_results=tuple(operation_results),
                        failed_step=step.name,
                    )

                run_results = []
                failed_item_index = None
                for item_index, item in enumerate(fan_out_items):
                    materialized = materialize_run_workflow(
                        step,
                        effective_workflow,
                        block_index=block_index,
                        step_index=step_index,
                        extra_bindings={"item": item} if step.for_each is not None else None,
                    )
                    if isinstance(materialized, Diagnostic):
                        diagnostics.append(materialized)
                        run_result = RuntimeResult(
                            mode=Mode.EXECUTE,
                            status=RuntimeStatus.EXECUTION_ERROR,
                            diagnostics=(materialized,),
                        )
                    else:
                        run_result = execute_workflow(
                            materialized,
                            profile=current_profile,
                            available_profiles=available_profiles,
                            profile_working_directories=profile_working_directories,
                            guard_probe=guard_probe,
                            step_executor=step_executor,
                            connector_provider=connector_provider,
                            invoked_by_run=True,
                            invoked_run_reference=step.run,
                        )
                    contextualized_run_diagnostics = (
                        _contextualize_fan_out_diagnostics(
                            run_result.diagnostics,
                            step=step,
                            item_index=item_index,
                            item=item,
                            item_count=len(fan_out_items),
                        )
                        if step.for_each is not None and run_result.diagnostics
                        else run_result.diagnostics
                    )
                    if contextualized_run_diagnostics is not run_result.diagnostics:
                        run_result = RuntimeResult(
                            mode=run_result.mode,
                            status=run_result.status,
                            diagnostics=contextualized_run_diagnostics,
                            plan=run_result.plan,
                            outputs=run_result.outputs,
                            results=run_result.results,
                            published=run_result.published,
                            operation_results=run_result.operation_results,
                            failed_guard=run_result.failed_guard,
                            failed_step=run_result.failed_step,
                            preflight_decision=run_result.preflight_decision,
                            analysis_tree=run_result.analysis_tree,
                        )
                    run_results.append(run_result)
                    diagnostics.extend(run_result.diagnostics)
                    operation_results.extend(run_result.operation_results)
                    propagated_profile = run_result.outputs.get("active_profile")
                    if effective_workflow.profile is None and materialized.profile is None and isinstance(propagated_profile, str) and available_profiles is not None and propagated_profile in available_profiles:
                        current_profile = available_profiles[propagated_profile]
                        current_profile_name = propagated_profile
                        current_working_directory = None if profile_working_directories is None else profile_working_directories.get(propagated_profile)
                        active_profile = propagated_profile
                        active_overrides = current_profile.overrides
                        applied = apply_profile_defaults_to_subsequent_steps(effective_workflow, current_profile)
                        effective_workflow = effective_workflow if applied.workflow is None else applied.workflow
                    executed_steps.extend([name for name in run_result.outputs.get("executed_steps", []) if isinstance(name, str)])
                    skipped_steps.extend([name for name in run_result.outputs.get("skipped_steps", []) if isinstance(name, str)])
                    step_condition_details.extend([detail for detail in run_result.outputs.get("step_condition_details", []) if isinstance(detail, dict)])
                    launcher_details.extend([detail for detail in run_result.outputs.get("launcher_details", []) if isinstance(detail, dict)])
                    checked_guards.extend([name for name in run_result.outputs.get("checked_guards", []) if isinstance(name, str)])
                    guard_details.extend([detail for detail in run_result.outputs.get("guard_details", []) if isinstance(detail, dict)])
                    published_results.extend(list(run_result.published))
                    if run_result.status is not RuntimeStatus.OK:
                        failed_item_index = item_index
                        break

                executed_steps.append(step.name)
                block_executed.append(step.name)
                if step.register is not None:
                    if step.for_each is None:
                        effective_workflow.step_results[step.register] = {"results": list(run_results[0].results)} if run_results else {"results": []}
                    else:
                        effective_workflow.step_results[step.register] = {
                            "results": [{"results": list(result.results)} for result in run_results]
                        }
                run_result = next((result for result in run_results if result.status is not RuntimeStatus.OK), run_results[-1] if run_results else RuntimeResult(mode=Mode.EXECUTE, status=RuntimeStatus.OK))
                if run_result.status is not RuntimeStatus.OK:
                    _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="failed")
                    skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index, current_step_index=step_index + 1))
                    _append_execution_error_block_item(
                        block_items,
                        block_index=block_index,
                        declared_block=declared_block,
                        executed_steps=block_executed,
                        skipped_steps=block_skipped,
                        failed_step=step.name,
                        failed_run=step.run,
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
                            step_gate_details=step_gate_details,
                            launcher_details=launcher_details,
                            checked_guards=checked_guards,
                            guard_details=guard_details,
                            block_items=block_items + _pending_execution_block_items(effective_workflow, start_block_index=block_index + 1, blocked=True),
                            extra={
                                "fan_out_failure": {
                                    "step": step.name,
                                    "item_index": failed_item_index,
                                    "item": fan_out_items[failed_item_index] if failed_item_index is not None and failed_item_index < len(fan_out_items) else None,
                                    "item_count": len(fan_out_items),
                                }
                                if step.for_each is not None
                                else None,
                            },
                        ),
                        operation_results=tuple(operation_results),
                        failed_guard=run_result.failed_guard,
                        failed_step=run_result.failed_step or step.name,
                    )
                _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="done")
                continue
            if isinstance(resolved_step, ResolvedBuiltinStep):
                if _is_execute_profile_switch_builtin(resolved_step):
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
                        _append_execution_error_block_item(
                            block_items,
                            block_index=block_index,
                            declared_block=declared_block,
                            executed_steps=block_executed,
                            skipped_steps=block_skipped,
                            failed_step=step.name,
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
                                step_gate_details=step_gate_details,
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
                    result = _execute_builtin_step(step, effective_workflow, observation_session=observation_session)
            else:
                if _is_execute_profile_switch_operation(resolved_step):
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
                        _append_execution_error_block_item(
                            block_items,
                            block_index=block_index,
                            declared_block=declared_block,
                            executed_steps=block_executed,
                            skipped_steps=block_skipped,
                            failed_step=step.name,
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
                                step_gate_details=step_gate_details,
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
            _record_step_runtime_result(
                workflow=effective_workflow,
                step=step,
                result=result,
                operation_results=operation_results,
                diagnostics=diagnostics,
            )
            if step.result is not None:
                workflow_results.append(result.outputs.get("value"))
            if step.publish is not None:
                published_results.append(result.outputs.get("value"))

            if result.status != "ok":
                _mark_execution_tree_step_runtime(execution_tree_output, step.name, runtime_status="failed")
                skipped_steps.extend(_remaining_step_names(effective_workflow, start_block_index=block_index, current_step_index=step_index + 1))
                _append_execution_error_block_item(
                    block_items,
                    block_index=block_index,
                    declared_block=declared_block,
                    executed_steps=block_executed,
                    skipped_steps=block_skipped,
                    failed_step=step.name,
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
                        step_gate_details=step_gate_details,
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

        _append_execution_ok_block_item(
            block_items,
            block_index=block_index,
            declared_block=declared_block,
            executed_steps=block_executed,
            skipped_steps=block_skipped,
        )

    results = tuple(workflow_results)
    if invoked_by_run and not results:
        results = (_nested_run_missing_result(workflow.workflow, run_reference=invoked_run_reference),)

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
            step_gate_details=step_gate_details,
            launcher_details=launcher_details,
            checked_guards=checked_guards,
            guard_details=guard_details,
            block_items=block_items,
        ),
        results=results,
        published=tuple(published_results),
        operation_results=tuple(operation_results),
    )


def _nested_run_missing_result(workflow_name: str, *, run_reference: str | None = None) -> JSONValue:
    display_name = Path(run_reference).stem if isinstance(run_reference, str) and run_reference else workflow_name
    return {
        "summary": f'Run-invoked workflow "{display_name}" completed without explicit result.',
        "workflow": display_name,
    }


def _evaluate_step_condition(step, workflow: Workflow, *, observation_session=None) -> bool | Diagnostic:
    value = evaluate_preflight_step_condition(
        step,
        workflow,
        step_results=workflow.step_results,
        observation_session=observation_session,
    )
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


def _evaluate_step_gate(step: Step, workflow: Workflow, *, observation_session=None) -> ConditionEvaluationReport | None:
    if step.gate is None:
        return None
    return evaluate_condition_report(
        step.gate,
        workflow,
        context=LocalExpressionContext.STEP_CONDITION,
        step_results=workflow.step_results,
        observation_session=observation_session,
        field_name="gate",
    )


def _gate_detail(step: Step, report: ConditionEvaluationReport, *, source: str, workflow: Workflow, step_results: dict[str, object]) -> dict[str, object]:
    detail = {
        "name": step.name,
        "gate": step.gate,
        "outcome": "passed" if report.verdict == "passed" else "blocked",
        "verdict": report.verdict,
        "source": source,
        "report": report.to_contract(),
        "failed": [node.to_contract() for node in report.failed],
        "failed_causes": [node.to_contract() for node in summarize_failed_condition_causes(report.root)],
        "unknown": [node.to_contract() for node in report.unknown],
        "unknown_causes": [node.to_contract() for node in summarize_unknown_condition_causes(report.root)],
        "passed": [node.to_contract() for node in report.passed],
    }
    if report.verdict == "failed":
        on_fail_context, on_fail_errors = evaluate_gate_failure_context(step, workflow, step_results=step_results)
        if on_fail_context:
            detail["on_fail_context"] = on_fail_context
        if on_fail_errors:
            detail["on_fail_context_errors"] = on_fail_errors
    return detail


def _gate_failure_diagnostic(step: Step, report: ConditionEvaluationReport, *, workflow: Workflow, step_results: dict[str, object]) -> Diagnostic:
    failed = [node.expression or node.to_contract().get("rendered") for node in summarize_failed_condition_causes(report.root) if isinstance(node.expression or node.to_contract().get("rendered"), str)]
    unknown = [node.expression or node.to_contract().get("rendered") for node in summarize_unknown_condition_causes(report.root) if isinstance(node.expression or node.to_contract().get("rendered"), str)]
    message = f"Step gate blocked execution for '{step.name}'"
    if report.verdict == "unknown":
        message = f"Step gate could not be fully established for '{step.name}'"
    details: dict[str, object] = {
        "step": step.name,
        "verdict": report.verdict,
        "failed_conditions": failed,
        "unknown_conditions": unknown,
    }
    if report.verdict == "failed":
        on_fail_context, on_fail_errors = evaluate_gate_failure_context(step, workflow, step_results=step_results)
        if on_fail_context:
            details["on_fail_context"] = on_fail_context
        if on_fail_errors:
            details["on_fail_context_errors"] = on_fail_errors
    return Diagnostic(
        code="runtime.step.gate.failed" if report.verdict == "failed" else "runtime.step.gate.unknown",
        level="error",
        message=message,
        path=("steps", step.name, "gate"),
        details=details,
    )


def _fan_out_gate_failure_human_summary(*, step_name: str, item: JSONValue, failed_conditions: list[str], unknown_conditions: list[str]) -> str:
    item_label = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, sort_keys=True)
    if failed_conditions:
        if len(failed_conditions) == 1:
            return f"Item '{item_label}' failed gate '{step_name}': {failed_conditions[0]}"
        rendered = "; ".join(failed_conditions)
        return f"Item '{item_label}' failed gate '{step_name}'. Failed conditions: {rendered}"
    if unknown_conditions:
        if len(unknown_conditions) == 1:
            return f"Item '{item_label}' could not establish gate '{step_name}': {unknown_conditions[0]}"
        rendered = "; ".join(unknown_conditions)
        return f"Item '{item_label}' could not establish gate '{step_name}'. Unknown conditions: {rendered}"
    return f"Item '{item_label}' failed gate '{step_name}'"


def _contextualize_fan_out_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    *,
    step: Step,
    item_index: int,
    item: JSONValue,
    item_count: int,
) -> tuple[Diagnostic, ...]:
    contextualized: list[Diagnostic] = []
    for diagnostic in diagnostics:
        details = dict(diagnostic.details)
        details.setdefault("fan_out_step", step.name)
        details.setdefault("fan_out_item_index", item_index)
        details.setdefault("fan_out_item", item)
        details.setdefault("fan_out_item_count", item_count)
        message = diagnostic.message
        if diagnostic.code in {"runtime.step.gate.failed", "runtime.step.gate.unknown"}:
            failed_conditions = [value for value in details.get("failed_conditions", []) if isinstance(value, str)]
            unknown_conditions = [value for value in details.get("unknown_conditions", []) if isinstance(value, str)]
            human_summary = _fan_out_gate_failure_human_summary(
                step_name=str(details.get("step", step.name)),
                item=item,
                failed_conditions=failed_conditions,
                unknown_conditions=unknown_conditions,
            )
            details.setdefault("human_summary", human_summary)
            message = human_summary
        contextualized.append(
            Diagnostic(
                code=diagnostic.code,
                level=diagnostic.level,
                message=message,
                path=diagnostic.path,
                details=details,
            )
        )
    return tuple(contextualized)


def _evaluate_run_for_each_items(
    step: Step,
    workflow: Workflow,
    *,
    block_index: int,
    step_index: int,
    observation_session=None,
) -> list[JSONValue] | Diagnostic:
    if step.for_each is None:
        return [None]
    try:
        value = resolve_runtime_value(
            step.for_each,
            workflow,
            allow_boolean_composition=True,
            observation_session=observation_session,
        )
    except ValueResolutionError as exc:
        return exc.to_diagnostic(path=("blocks", str(block_index), "steps", str(step_index), "for_each"))
    if not isinstance(value, list):
        return Diagnostic(
            code="runtime.run.for_each.not_array",
            level="error",
            message="Run field 'for_each' must resolve to an array value",
            path=("blocks", str(block_index), "steps", str(step_index), "for_each"),
            details={"actual_type": type(value).__name__},
        )
    return value


def _default_step_executor(*, provider: ConnectorProvider | None):
    """Default executor backed by canonical connector operations."""

    def execute(resolved_step: ResolvedOperation, workflow: Workflow) -> OperationResult:
        if resolved_step.connector_namespace == "routine":
            return execute_routine_step(resolved_step, workflow)
        resolved_provider = provider or get_default_connector_provider()
        return resolved_provider.step_executor(resolved_step, workflow)

    return execute


def _initialize_execute_context(
    workflow: Workflow,
    *,
    profile: Profile | None,
    available_profiles: dict[str, Profile] | None = None,
    profile_working_directories: dict[str, Path | None] | None,
) -> dict[str, object]:
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
    if workflow.profile is not None:
        if profile is not None and workflow.profile == profile.name:
            current_profile = profile
            current_profile_name = profile.name
            active_profile = profile.name
            active_overrides = profile.overrides
        elif available_profiles is not None and workflow.profile in available_profiles:
            current_profile = available_profiles[workflow.profile]
            current_profile_name = current_profile.name
            active_profile = current_profile.name
            active_overrides = current_profile.overrides
            applied = apply_runtime_profile_switch(effective_workflow, current_profile)
            if applied.ok and applied.workflow is not None:
                effective_workflow = applied.workflow
    current_working_directory = None if current_profile_name is None or profile_working_directories is None else profile_working_directories.get(current_profile_name)
    return {
        "workflow": effective_workflow,
        "active_profile": active_profile,
        "active_overrides": active_overrides,
        "current_profile": current_profile,
        "current_profile_name": current_profile_name,
        "current_working_directory": current_working_directory,
    }


def _record_step_runtime_result(
    *,
    workflow: Workflow,
    step: Step,
    result: OperationResult,
    operation_results: list[OperationResult],
    diagnostics: list[Diagnostic],
) -> None:
    if step.register is not None:
        workflow.step_results[step.register] = {
            "status": result.status,
            "summary": result.summary,
            "outputs": dict(result.outputs),
        }
    operation_results.append(result)
    diagnostics.extend(result.diagnostics)


def _append_execution_error_block_item(
    block_items: list[dict[str, object]],
    *,
    block_index: int,
    declared_block: StepBlock,
    executed_steps: list[str],
    skipped_steps: list[str],
    failed_step: str,
    failed_run: str | None = None,
) -> None:
    payload = {
        "block_index": block_index,
        "type": "steps",
        "status": "execution_error",
        "step_names": [candidate.name for candidate in declared_block.steps],
        "executed_steps": executed_steps,
        "skipped_steps": skipped_steps,
        "failed_step": failed_step,
    }
    if failed_run is not None:
        payload["failed_run"] = failed_run
    block_items.append(payload)


def _append_execution_ok_block_item(
    block_items: list[dict[str, object]],
    *,
    block_index: int,
    declared_block: StepBlock,
    executed_steps: list[str],
    skipped_steps: list[str],
) -> None:
    block_items.append(
        {
            "block_index": block_index,
            "type": "steps",
            "status": "ok",
            "step_names": [candidate.name for candidate in declared_block.steps],
            "executed_steps": executed_steps,
            "skipped_steps": skipped_steps,
        }
    )


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
            OperationResult(status="input_error", summary=exc.message, diagnostics=exc.to_diagnostics()),
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
    applied = apply_runtime_profile_switch(workflow, target_profile)
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


def _execute_builtin_step(step, workflow: Workflow, *, observation_session=None) -> OperationResult:
    try:
        if step.value is not None:
            return _execute_value_step(step.name, step.value, workflow, observation_session=observation_session)
        if step.operation is None and step.run is None and step.steps is None and step.profile_switch is None and step.value is None and step.result is None and step.publish is None and step.state_set is None and step.state_delete is None:
            return OperationResult(status="ok", summary=f"Gate checkpoint step '{step.name}' passed", outputs={})
        if step.result is not None:
            return _execute_result_step(step.name, step.result, workflow, observation_session=observation_session)
        if step.publish is not None:
            return _execute_publish_step(step.name, step.publish, workflow, observation_session=observation_session)
        if step.state_set is not None:
            return _execute_state_set(step.name, step.state_set, workflow, observation_session=observation_session)
        if step.state_delete is not None:
            return _execute_state_delete(step.name, step.state_delete, workflow)
    except RuntimeStateError as exc:
        return OperationResult(status="state_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))
    except ValueResolutionError as exc:
        return OperationResult(status="state_error", summary=exc.message, diagnostics=exc.to_diagnostics())
    return OperationResult(status="state_error", summary="Unknown builtin step form")


def _execute_value_step(step_name: str, raw_value: JSONValue, workflow: Workflow, *, observation_session=None) -> OperationResult:
    return evaluate_preflight_value_step(
        Step(name=step_name, value=raw_value),
        workflow,
        observation_session=observation_session,
    )


def _execute_publish_step(step_name: str, raw_value: JSONValue, workflow: Workflow, *, observation_session=None) -> OperationResult:
    value = resolve_runtime_value(raw_value, workflow, observation_session=observation_session)
    return OperationResult(
        status="ok",
        summary=f"Published workflow output for step '{step_name}'",
        outputs={"value": value},
    )


def _execute_result_step(step_name: str, raw_value: JSONValue, workflow: Workflow, *, observation_session=None) -> OperationResult:
    value = resolve_runtime_value(raw_value, workflow, observation_session=observation_session)
    return OperationResult(
        status="ok",
        summary=f"Recorded workflow result for step '{step_name}'",
        outputs={"value": value},
    )


def _execute_state_set(step_name: str, state_set: dict[str, JSONValue], workflow: Workflow, *, observation_session=None) -> OperationResult:
    target_expr, raw_value = next(iter(state_set.items()))
    target = resolve_state_target(target_expr, workflow, step_results=workflow.step_results, observation_session=observation_session)
    value = resolve_runtime_value(raw_value, workflow, observation_session=observation_session)
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
    target = resolve_state_target(target_expr, workflow, step_results=workflow.step_results)
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
            child["runtime_probe_result"] = child.get("planned_probe_result")
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
                child["runtime_probe_result"] = runtime
                planned = child.get("planned_probe_result")
                matches = planned in (None, {}, runtime)
                child["divergence_status"] = "matched" if matches else "diverged"
                child["divergence_reason"] = None if matches else "runtime_probe_result_mismatch"
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
            child["runtime_probe_result"] = dict(result.outputs)
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
            planned = child.get("planned_probe_result")
            runtime = dict(result.outputs)
            child["runtime_status"] = "revalidated"
            child["revalidated"] = True
            child["runtime_probe_result"] = runtime
            child["divergence_status"] = "matched" if planned == runtime else "diverged"
            child["divergence_reason"] = None if planned == runtime else "runtime_probe_result_mismatch"
            _refresh_execution_tree_block_runtime(block)
            return


def _condition_source_from_tree_state(step: Step, workflow: Workflow, execution_tree: dict[str, object] | None) -> str:
    if step.if_ is None or not isinstance(execution_tree, dict):
        return "runtime"
    if not _condition_mentions_step_results(step.if_):
        return "runtime"
    return "execution_tree_state" if bool(workflow.step_results) else "runtime"


def _condition_mentions_step_results(value: JSONValue) -> bool:
    if isinstance(value, str):
        return "step." in value
    try:
        normalized = normalize_condition_authoring(value)
    except ConditionShapeError:
        return False
    return any("step." in expression for _, expression in iter_condition_expression_leaves(normalized))


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


def _prepare_tree_driven_step_context(
    *,
    step: Step,
    workflow: Workflow,
    execution_tree: dict[str, object] | None,
    preflight_reuse: dict[str, dict[str, object]],
    block_index: int,
    step_index: int,
) -> dict[str, object]:
    return {
        "should_execute": _should_execute_step_from_tree(
            execution_tree,
            block_index=block_index,
            step_index=step_index,
            step_name=step.name,
        ),
        "reused_preflight": preflight_reuse.get(step.name),
        "condition_source": _condition_source_from_tree_state(step, workflow, execution_tree),
    }


def _is_execute_probe_step(execution_tree: dict[str, object] | None, resolved_step: object) -> bool:
    return (
        execution_tree is not None
        and isinstance(resolved_step, ResolvedOperation)
        and resolved_step.operation.kind == "probe"
        and resolved_step.connector_namespace != "routine"
    )


def _is_execute_run_step(resolved_step: object) -> bool:
    return isinstance(resolved_step, ResolvedRunStep)


def _is_execute_profile_switch_builtin(resolved_step: ResolvedBuiltinStep) -> bool:
    return resolved_step.builtin == "profile_switch"


def _is_execute_profile_switch_operation(resolved_step: ResolvedOperation) -> bool:
    return resolved_step.reference == "runtime.profile.use"


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
    step_gate_details: list[dict[str, object]],
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
        "step_gate_details": step_gate_details,
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
