"""Check mode for pre-execution validation, local-expression-aware resolution, and guard analysis."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import cast

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, PreflightBlockNode, PreflightDecisionModel, PreflightGuardNode, RuntimeResult, RuntimeStatus
from ordo.model.workflow import GuardBlock, Step, StepBlock, Workflow

from .fragment_runs import CheckRunExpansionDecision, classify_run_for_check
from .local_expression_engine.core import AdapterBindingNode, AdapterInvocationNode, BinaryNode, BuiltinCallNode, CallArgumentNode, CallNode, ConditionObservationRequest, ConditionObservationResult, FilterApplicationNode, ListNode, LiteralNode, LocalExpressionParseError, ObjectEntryNode, ObjectNode, OnlyPredicateNode, PipelineNode, ReadOnlyObservationSession, ReferenceNode, UnaryNode, ValueExpressionNode, evaluate_condition_expression, parse_local_expression_tree, render_expression_text
from .local_expressions import extract_embedded_local_expression
from .launchers import validate_step_launchers
from .preflight_interpreter import build_preflight_halt, evaluate_preflight_probe_step, evaluate_preflight_step_condition, evaluate_preflight_value_step, store_preflight_register_output
from .preflight_steps import classify_preflight_step
from .profiles import apply_profile_defaults_to_subsequent_steps, apply_profile_to_workflow
from .providers import ConnectorProvider, GuardProbe, get_default_connector_provider
from .resolution import ResolvedBuiltinStep, ResolvedConditionExpression, ResolvedExpressionProbe, ResolvedGuardBlock, ResolvedOperation, ResolvedRunStep, ResolvedStep, ResolvedStepBlock, resolve_workflow_references
from .value_resolution import ValueResolutionError, resolve_runtime_value
from .validation import validate_workflow_document, validate_workflow_semantics


_ACTION_PLACEHOLDER_PATTERN = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_INPUT_REFERENCE_PATTERN = re.compile(r"\binputs\.([A-Za-z_][A-Za-z0-9_]*)\b")


@dataclass(frozen=True, slots=True)
class _CheckAnalysisTree:
    """Shared internal preflight-analysis tree extracted from check."""

    workflow: Workflow
    initial_resolution: object
    active_profile: str | None
    active_overrides: tuple[object, ...]
    diagnostics: tuple[Diagnostic, ...]
    operation_results: tuple[OperationResult, ...]
    blockers: tuple[str, ...]
    checked_guards: tuple[str, ...]
    guard_details: tuple[dict[str, object], ...]
    block_items: tuple[dict[str, object], ...]
    preflight_step_items: tuple[dict[str, object], ...]
    preflight_halts: tuple[dict[str, object], ...]
    bootstrap_details: tuple[dict[str, object], ...]
    incomplete_reasons: tuple[str, ...]
    observed_probe_calls: tuple[dict[str, object], ...]
    input_usages: tuple[dict[str, object], ...]
    failed_guard: str | None = None


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
        "preflight_registers": {},
        "preflight_step_results": {},
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


def _build_preflight_decision_model(workflow: Workflow, outputs: dict[str, object]) -> PreflightDecisionModel:
    coverage_by_reference = {
        item["reference"]: item
        for item in outputs.get("guard_coverage", [])
        if isinstance(item, dict) and isinstance(item.get("reference"), str)
    }
    guard_nodes: list[PreflightGuardNode] = []
    for block_index, block in enumerate(workflow.blocks):
        if not isinstance(block, GuardBlock):
            continue
        for guard in block.guards:
            coverage = coverage_by_reference.get(guard.reference, {})
            guard_nodes.append(
                PreflightGuardNode(
                    reference=guard.reference,
                    block_index=block_index,
                    relevant=bool(coverage.get("relevant", True)),
                    evaluated=bool(coverage.get("evaluated", False)),
                    status=str(coverage.get("status", "pending")),
                    unknown_reason=cast(str | None, coverage.get("unknown_reason")),
                )
            )

    block_nodes: list[PreflightBlockNode] = []
    for item in outputs.get("block_items", []):
        if not isinstance(item, dict):
            continue
        block_index = item.get("block_index")
        block_type = item.get("type")
        status = item.get("status")
        if not isinstance(block_index, int) or not isinstance(block_type, str) or not isinstance(status, str):
            continue
        guard_references = tuple(
            reference for reference in item.get("guard_references", []) if isinstance(reference, str)
        )
        step_names = tuple(name for name in item.get("step_names", []) if isinstance(name, str))
        block_nodes.append(
                PreflightBlockNode(
                    block_index=block_index,
                    block_type=block_type,
                    status=status,
                    active_profile=cast(str | None, item.get("active_profile")),
                    guard_references=guard_references,
                    step_names=step_names,
                )
        )

    return PreflightDecisionModel(
        allowed_state=str(outputs.get("allowed_state", "blocked")),
        analysis_complete=bool(outputs.get("analysis_complete", False)),
        incomplete_reasons=tuple(reason for reason in outputs.get("incomplete_reasons", []) if isinstance(reason, str)),
        guard_nodes=tuple(guard_nodes),
        block_nodes=tuple(block_nodes),
    )


def check_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    available_profiles: dict[str, Profile] | None = None,
    profile_working_directories: dict[str, Path | None] | None = None,
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
    current_profile = profile
    current_profile_name = None if profile is None else profile.name

    if profile is not None:
        applied = apply_profile_to_workflow(workflow, profile)
        active_profile = applied.active_profile
        active_overrides = applied.active_overrides
        current_profile_name = applied.active_profile
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
        current_profile = profile

    semantic_report = validate_workflow_semantics(effective_workflow)
    if not semantic_report.ok:
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.VALIDATION_ERROR,
            diagnostics=semantic_report.diagnostics,
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

    analysis = _build_check_analysis_tree(
        workflow=effective_workflow,
        active_profile=active_profile,
        current_profile=current_profile,
        available_profiles=available_profiles,
        profile_working_directories=profile_working_directories,
        active_overrides=active_overrides,
        connector_provider=connector_provider,
        guard_probe=guard_probe,
    )
    if isinstance(analysis, RuntimeResult):
        return analysis

    return _project_check_runtime_result(analysis)


def _project_check_runtime_result(analysis: _CheckAnalysisTree) -> RuntimeResult:
    effective_workflow = analysis.workflow

    if analysis.blockers:
        observation_basis = _build_observation_basis_outputs(effective_workflow, analysis.initial_resolution, list(analysis.guard_details))
        outputs = {
            **_base_verdict_outputs(can_execute=False, allowed_state="blocked", analysis_complete=True),
            "blockers": list(analysis.blockers),
            "checked_guards": list(analysis.checked_guards),
            **_guard_coverage_outputs(effective_workflow, checked_guards=list(analysis.checked_guards), blockers=list(analysis.blockers)),
            **observation_basis,
            "guard_details": list(analysis.guard_details),
            "block_items": list(analysis.block_items),
            "preflight_step_items": list(analysis.preflight_step_items),
            "preflight_halts": list(analysis.preflight_halts),
            "preflight_registers": dict(effective_workflow.step_results),
            "preflight_step_results": dict(effective_workflow.step_results),
            "active_profile": analysis.active_profile,
            "active_overrides": [override.to_contract() for override in analysis.active_overrides],
        }
        if analysis.bootstrap_details:
            outputs["bootstrap_details"] = list(analysis.bootstrap_details)
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.GUARD_FAILED,
            diagnostics=analysis.diagnostics,
            plan=ExecutionPlan(
                guard_checks=analysis.checked_guards,
                step_names=tuple(_all_step_names(effective_workflow)),
                blockers=analysis.blockers,
            ),
            outputs=outputs,
            operation_results=analysis.operation_results,
            failed_guard=analysis.failed_guard,
            preflight_decision=_build_preflight_decision_model(effective_workflow, outputs),
            analysis_tree=analysis,
        )

    outputs = {
        **_base_verdict_outputs(
            can_execute=not analysis.incomplete_reasons,
            allowed_state="unknown" if analysis.incomplete_reasons else "allowed",
            analysis_complete=not analysis.incomplete_reasons,
            incomplete_reasons=list(analysis.incomplete_reasons),
        ),
        "blockers": [],
        "checked_guards": list(analysis.checked_guards),
        **_guard_coverage_outputs(effective_workflow, checked_guards=list(analysis.checked_guards), blockers=[]),
        **_build_observation_basis_outputs(effective_workflow, analysis.initial_resolution, list(analysis.guard_details)),
        "guard_details": list(analysis.guard_details),
        "block_items": list(analysis.block_items),
        "preflight_step_items": list(analysis.preflight_step_items),
        "preflight_halts": list(analysis.preflight_halts),
        "preflight_registers": dict(effective_workflow.step_results),
        "preflight_step_results": dict(effective_workflow.step_results),
        "active_profile": analysis.active_profile,
        "active_overrides": [override.to_contract() for override in analysis.active_overrides],
    }
    if analysis.bootstrap_details:
        outputs["bootstrap_details"] = list(analysis.bootstrap_details)

    return RuntimeResult(
        mode=Mode.CHECK,
        status=RuntimeStatus.OK,
        diagnostics=analysis.diagnostics,
        plan=ExecutionPlan(
            guard_checks=analysis.checked_guards,
            step_names=tuple(_all_step_names(effective_workflow)),
            blockers=(),
        ),
        outputs=outputs,
        operation_results=analysis.operation_results,
        preflight_decision=_build_preflight_decision_model(effective_workflow, outputs),
        analysis_tree=analysis,
    )


def _build_check_analysis_tree(
    *,
    workflow: Workflow,
    active_profile: str | None,
    current_profile: Profile | None,
    available_profiles: dict[str, Profile] | None,
    profile_working_directories: dict[str, Path | None] | None = None,
    active_overrides,
    connector_provider: ConnectorProvider | None,
    guard_probe: GuardProbe | None,
) -> _CheckAnalysisTree | RuntimeResult:
    probe = guard_probe or _default_guard_probe(provider=connector_provider)
    diagnostics: list[Diagnostic] = []
    operation_results: list[OperationResult] = []
    blockers: list[str] = []
    checked_guards: list[str] = []
    guard_details: list[dict[str, object]] = []
    block_items: list[dict[str, object]] = []
    preflight_step_items: list[dict[str, object]] = []
    preflight_halts: list[dict[str, object]] = []
    bootstrap_details: list[dict[str, object]] = []
    failed_guard: str | None = None
    incomplete_reasons: list[str] = []
    observed_probe_calls: list[dict[str, object]] = []

    current_profile_name = active_profile
    effective_workflow = workflow
    resolved_overrides = active_overrides
    current_working_directory = (
        None
        if current_profile_name is None or profile_working_directories is None
        else profile_working_directories.get(current_profile_name)
    )
    halted = False
    initial_resolution = resolve_workflow_references(
        effective_workflow,
        connector_provider=connector_provider,
        active_overrides=resolved_overrides,
    )
    if not initial_resolution.ok:
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.RESOLUTION_ERROR,
            diagnostics=initial_resolution.diagnostics,
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
                "active_overrides": [override.to_contract() for override in resolved_overrides],
            },
        )

    for block_index, declared_block in enumerate(effective_workflow.blocks):
        if isinstance(declared_block, GuardBlock):
            if halted:
                block_items.append(_pending_guard_block_item_from_declared(block_index, declared_block, current_profile_name))
                continue
            resolved_block = _resolve_guard_block(
                effective_workflow,
                block_index=block_index,
                connector_provider=connector_provider,
                active_overrides=resolved_overrides,
            )
            if isinstance(resolved_block, RuntimeResult):
                return resolved_block
            block_blockers: list[str] = []
            block_guard_details: list[dict[str, object]] = []
            for resolved_guard in resolved_block.guards:
                if isinstance(resolved_guard, ResolvedConditionExpression):
                    with _checking_working_directory(current_working_directory):
                        result = _evaluate_guard_expression(resolved_guard, effective_workflow, probe)
                else:
                    with _checking_working_directory(current_working_directory):
                        result = probe(resolved_guard, effective_workflow)
                operation_results.append(result)
                diagnostics.extend(result.diagnostics)
                detail = _build_guard_detail(
                    resolved_guard.reference,
                    result,
                    observation_scopes=_guard_observation_scopes(resolved_guard),
                    observations=_guard_observations(resolved_guard),
                )
                guard_details.append(detail)
                block_guard_details.append(detail)
                checked_guards.append(resolved_guard.reference)
                observed_probe_calls.extend(item for item in detail.get("observations", []) if isinstance(item, dict))
                bootstrap_details = _collect_bootstrap_details(operation_results)
                if result.status != "ok":
                    blockers.append(resolved_guard.reference)
                    block_blockers.append(resolved_guard.reference)
                    if failed_guard is None:
                        failed_guard = resolved_guard.reference
            block_items.append(
                {
                    "block_index": block_index,
                    "type": "guards",
                    "status": "blocked" if block_blockers else "ok",
                    "guard_references": [guard.reference for guard in resolved_block.guards],
                    "blockers": block_blockers,
                    "guard_details": block_guard_details,
                    "active_profile": current_profile_name,
                }
            )
            if block_blockers:
                halted = True
            continue

        if _is_static_profile_switch_block(declared_block):
            if halted and blockers:
                block_items.append(_pending_step_block_item_from_declared(block_index, declared_block, blocked=True, active_profile=current_profile_name))
                continue
            transition = _apply_static_profile_switch_block(
                declared_block,
                workflow=effective_workflow,
                available_profiles=available_profiles,
            )
            if transition is None:
                block_items.append(_pending_step_block_item_from_declared(block_index, declared_block, blocked=False, active_profile=current_profile_name))
                halted = True
                incomplete_reasons.append("profile_switch_not_resolvable_from_current_knowledge")
                continue
            current_profile_name, current_profile, resolved_overrides, effective_workflow = transition
            active_profile = current_profile_name
            current_working_directory = (
                None
                if current_profile_name is None or profile_working_directories is None
                else profile_working_directories.get(current_profile_name)
            )
            halted = False
            block_items.append(
                {
                    "block_index": block_index,
                    "type": "steps",
                    "status": "context_applied",
                    "step_names": [step.name for step in declared_block.steps],
                    "conditional_steps": [step.name for step in declared_block.steps if step.if_ is not None],
                    "active_profile": current_profile_name,
                }
            )
            continue

        run_expansions = _classify_run_step_block_for_check(declared_block, effective_workflow, block_index=block_index)
        if run_expansions is not None:
            if halted:
                block_items.append(_pending_step_block_item_from_declared(block_index, declared_block, blocked=True, active_profile=current_profile_name))
                continue
            block_items.append(
                {
                    "block_index": block_index,
                    "type": "steps",
                    "status": "expanded",
                    "step_names": [step.name for step in declared_block.steps],
                    "conditional_steps": [],
                    "active_profile": current_profile_name,
                }
            )
            expansion_outcome = _expand_run_step_block_for_check(
                run_expansions,
                current_workflow=effective_workflow,
                current_profile_name=current_profile_name,
                current_profile=current_profile,
                active_overrides=resolved_overrides,
                available_profiles=available_profiles,
                profile_working_directories=profile_working_directories,
                connector_provider=connector_provider,
            )
            diagnostics.extend(expansion_outcome["diagnostics"])
            operation_results.extend(expansion_outcome["operation_results"])
            checked_guards.extend(expansion_outcome["checked_guards"])
            guard_details.extend(expansion_outcome["guard_details"])
            block_items.extend(expansion_outcome["block_items"])
            blockers.extend(expansion_outcome["blockers"])
            incomplete_reasons.extend(expansion_outcome["incomplete_reasons"])
            bootstrap_details = _collect_bootstrap_details(operation_results)
            effective_workflow = cast(Workflow, expansion_outcome["workflow"])
            current_profile_name = cast(str | None, expansion_outcome["current_profile_name"])
            current_profile = cast(Profile | None, expansion_outcome["current_profile"])
            resolved_overrides = cast(tuple, expansion_outcome["active_overrides"])
            current_working_directory = cast(Path | None, expansion_outcome.get("current_working_directory", current_working_directory))
            active_profile = current_profile_name
            if expansion_outcome["failed_guard"] is not None and failed_guard is None:
                failed_guard = cast(str, expansion_outcome["failed_guard"])
            if expansion_outcome["halted"]:
                halted = True
            continue

        if _has_later_guard_block(effective_workflow, block_index=block_index):
            interpreted_step_block = _interpret_step_block_for_check(
                declared_block,
                effective_workflow,
                block_index=block_index,
                current_profile_name=current_profile_name,
                current_profile=current_profile,
                connector_provider=connector_provider,
                probe=probe,
                active_overrides=resolved_overrides,
                available_profiles=available_profiles,
                profile_working_directories=profile_working_directories,
                current_working_directory=current_working_directory,
                observed_probe_calls=observed_probe_calls,
            )
            if interpreted_step_block is not None:
                if interpreted_step_block.get("resolution_error") is not None:
                    return cast(RuntimeResult, interpreted_step_block["resolution_error"])
                diagnostics.extend(interpreted_step_block["diagnostics"])
                block_items.append(interpreted_step_block["block_item"])
                preflight_step_items.extend(cast(list[dict[str, object]], interpreted_step_block["step_items"]))
                preflight_halts.extend(cast(list[dict[str, object]], interpreted_step_block["halts"]))
                incomplete_reasons.extend(interpreted_step_block["incomplete_reasons"])
                effective_workflow = cast(Workflow, interpreted_step_block.get("workflow", effective_workflow))
                current_profile_name = cast(str | None, interpreted_step_block.get("current_profile_name", current_profile_name))
                current_profile = cast(Profile | None, interpreted_step_block.get("current_profile", current_profile))
                resolved_overrides = cast(tuple, interpreted_step_block.get("active_overrides", resolved_overrides))
                current_working_directory = cast(Path | None, interpreted_step_block.get("current_working_directory", current_working_directory))
                active_profile = current_profile_name
                if interpreted_step_block["halted"]:
                    halted = True
                continue

        if halted:
            block_items.append(_pending_step_block_item_from_declared(block_index, declared_block, blocked=True, active_profile=current_profile_name))
            continue
        block_items.append(_pending_step_block_item_from_declared(block_index, declared_block, blocked=False, active_profile=current_profile_name))
        halted = True

    if not blockers and any(item.get("type") == "guards" and item.get("status") == "pending" for item in block_items):
        incomplete_reasons.append("relevant_guard_coverage_incomplete")
        if _has_pre_run_before_pending_guards(block_items):
            incomplete_reasons.append("pre_run_precedes_main_guard_coverage")

    if halted and len(block_items) < len(effective_workflow.blocks):
        block_items.extend(_build_pending_block_items(effective_workflow, blocked=bool(blockers), start_index=len(block_items), active_profile=current_profile_name))

    structural_fill_result = _append_structural_items_for_uninterpreted_step_blocks(
        workflow=effective_workflow,
        block_items=block_items,
        preflight_step_items=preflight_step_items,
        connector_provider=connector_provider,
        active_overrides=resolved_overrides,
        observed_probe_calls=observed_probe_calls,
    )
    if structural_fill_result is not None:
        return structural_fill_result

    return _CheckAnalysisTree(
        workflow=effective_workflow,
        initial_resolution=initial_resolution,
        active_profile=active_profile,
        active_overrides=tuple(resolved_overrides),
        diagnostics=tuple(diagnostics),
        operation_results=tuple(operation_results),
        blockers=tuple(blockers),
        checked_guards=tuple(checked_guards),
        guard_details=tuple(guard_details),
        block_items=tuple(block_items),
        preflight_step_items=tuple(preflight_step_items),
        preflight_halts=tuple(preflight_halts),
        bootstrap_details=tuple(bootstrap_details),
        incomplete_reasons=tuple(incomplete_reasons),
        observed_probe_calls=tuple(observed_probe_calls),
        input_usages=_classify_declared_input_usage(
            effective_workflow,
            connector_provider=connector_provider,
            active_overrides=resolved_overrides,
        ),
        failed_guard=failed_guard,
    )


def _classify_declared_input_usage(
    workflow: Workflow,
    *,
    connector_provider: ConnectorProvider | None,
    active_overrides,
) -> tuple[dict[str, object], ...]:
    declared_inputs = [name for name in workflow.declared_inputs if isinstance(name, str)]
    if not declared_inputs:
        return ()

    evidence_by_input: dict[str, list[dict[str, object]]] = {name: [] for name in declared_inputs}
    classification_rank = {"unused_input": 0, "effect_target_input": 1, "contract_input": 2, "control_input": 3}
    classification_by_input = {name: "unused_input" for name in declared_inputs}

    def record(input_name: str, classification: str, *, site_kind: str, path: tuple[object, ...], detail: str) -> None:
        if input_name not in evidence_by_input:
            return
        evidence_by_input[input_name].append(
            {
                "site_kind": site_kind,
                "path": [str(part) for part in path],
                "detail": detail,
            }
        )
        if classification_rank[classification] > classification_rank[classification_by_input[input_name]]:
            classification_by_input[input_name] = classification

    resolution = resolve_workflow_references(
        workflow,
        connector_provider=connector_provider,
        active_overrides=active_overrides,
    )
    resolved_blocks = resolution.blocks if resolution.ok else ()

    for block_index, block in enumerate(workflow.blocks):
        resolved_block = resolved_blocks[block_index] if block_index < len(resolved_blocks) else None
        if isinstance(block, GuardBlock):
            for guard_index, guard in enumerate(block.guards):
                for input_name in _extract_input_names(guard.expr):
                    record(
                        input_name,
                        "control_input",
                        site_kind="guard_expr",
                        path=("blocks", block_index, "guards", guard_index),
                        detail=guard.reference,
                    )
                if guard.operation is not None:
                    for input_name in _extract_input_names(guard.operation.with_):
                        record(
                            input_name,
                            "control_input",
                            site_kind="guard_target",
                            path=("blocks", block_index, "guards", guard_index, "with"),
                            detail=guard.operation.uses,
                        )
            continue
        if isinstance(block, StepBlock):
            resolved_steps = resolved_block.steps if isinstance(resolved_block, ResolvedStepBlock) else ()
            for step_index, step in enumerate(block.steps):
                resolved_step = resolved_steps[step_index] if step_index < len(resolved_steps) else None
                for input_name in _extract_input_names(step.if_):
                    record(
                        input_name,
                        "control_input",
                        site_kind="step_condition",
                        path=("blocks", block_index, "steps", step_index, "if"),
                        detail=step.name,
                    )
                if step.profile_switch is not None:
                    for input_name in _extract_input_names(step.profile_switch):
                        record(
                            input_name,
                            "control_input",
                            site_kind="profile_switch",
                            path=("blocks", block_index, "steps", step_index, "profile_switch"),
                            detail=step.name,
                        )
                if step.state_set is not None:
                    for input_name in _extract_input_names(step.state_set):
                        record(
                            input_name,
                            "control_input",
                            site_kind="state_set",
                            path=("blocks", block_index, "steps", step_index, "state_set"),
                            detail=step.name,
                        )
                if step.value is not None:
                    for input_name in _extract_input_names(step.value):
                        record(
                            input_name,
                            "contract_input",
                            site_kind="value",
                            path=("blocks", block_index, "steps", step_index, "value"),
                            detail=step.name,
                        )
                if step.publish is not None:
                    for input_name in _extract_input_names(step.publish):
                        record(
                            input_name,
                            "contract_input",
                            site_kind="publish",
                            path=("blocks", block_index, "steps", step_index, "publish"),
                            detail=step.name,
                        )
                if step.result is not None:
                    for input_name in _extract_input_names(step.result):
                        record(
                            input_name,
                            "contract_input",
                            site_kind="result",
                            path=("blocks", block_index, "steps", step_index, "result"),
                            detail=step.name,
                        )
                if step.run is not None:
                    for input_name in _extract_input_names(step.run_with):
                        record(
                            input_name,
                            "effect_target_input",
                            site_kind="run_with",
                            path=("blocks", block_index, "steps", step_index, "with"),
                            detail=step.name,
                        )
                if step.operation is not None:
                    step_kind = resolved_step.operation.kind if isinstance(resolved_step, ResolvedOperation) else "unknown"
                    for input_name in _extract_input_names(step.operation.with_):
                        record(
                            input_name,
                            "effect_target_input",
                            site_kind="operation_target",
                            path=("blocks", block_index, "steps", step_index, "with"),
                            detail=f"{step.operation.uses}:{step_kind}",
                        )

    return tuple(
        {
            "input": input_name,
            "classification": classification_by_input[input_name],
            "evidence": evidence_by_input[input_name],
        }
        for input_name in declared_inputs
    )


def _extract_input_names(value: JSONValue | dict[str, object] | None) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return _extract_input_names_from_string(value)
    if isinstance(value, dict):
        names: set[str] = set()
        for key, nested in value.items():
            names.update(_extract_input_names(key))
            names.update(_extract_input_names(cast(JSONValue, nested)))
        return names
    if isinstance(value, list):
        names: set[str] = set()
        for nested in value:
            names.update(_extract_input_names(cast(JSONValue, nested)))
        return names
    return set()


def _extract_input_names_from_string(value: str) -> set[str]:
    names = set(_INPUT_REFERENCE_PATTERN.findall(value))
    expression = value[2:-1] if value.startswith("${") and value.endswith("}") and len(value) >= 4 else value
    try:
        parsed = parse_local_expression_tree(expression)
    except LocalExpressionParseError:
        return names
    names.update(_collect_input_names_from_expression_node(parsed.root))
    return names


def _collect_input_names_from_expression_node(node: ValueExpressionNode) -> set[str]:
    names: set[str] = set()

    def visit(current: ValueExpressionNode) -> None:
        if isinstance(current, ReferenceNode):
            if len(current.parts) >= 2 and current.parts[0] == "inputs":
                names.add(current.parts[1])
            return
        if isinstance(current, ListNode):
            for item in current.items:
                visit(item)
            return
        if isinstance(current, ObjectEntryNode):
            visit(current.value)
            return
        if isinstance(current, ObjectNode):
            for entry in current.entries:
                visit(entry)
            return
        if isinstance(current, CallArgumentNode):
            visit(current.value)
            return
        if isinstance(current, CallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, PipelineNode):
            visit(current.source)
            for item in current.filters:
                visit(item)
            return
        if isinstance(current, FilterApplicationNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, OnlyPredicateNode):
            visit(current.expected)
            return
        if isinstance(current, BuiltinCallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, UnaryNode):
            visit(current.operand)
            return
        if isinstance(current, BinaryNode):
            visit(current.left)
            visit(current.right)
            return
        if isinstance(current, AdapterBindingNode):
            visit(current.value)
            return
        if isinstance(current, AdapterInvocationNode):
            for binding in current.bindings:
                visit(binding)
            return

    visit(node)
    return names


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


def _resolve_guard_block(
    workflow: Workflow,
    *,
    block_index: int,
    connector_provider: ConnectorProvider | None,
    active_overrides,
) -> ResolvedGuardBlock | RuntimeResult:
    block = workflow.blocks[block_index]
    assert isinstance(block, GuardBlock)
    resolution = resolve_workflow_references(
        Workflow(
            version=workflow.version,
            workflow=workflow.workflow,
            inputs=workflow.inputs,
            declared_inputs=workflow.declared_inputs,
            explicit_input_keys=workflow.explicit_input_keys,
            let_bindings=workflow.let_bindings,
            state_needs=workflow.state_needs,
            state_bindings=workflow.state_bindings,
            states=workflow.states,
            step_results=workflow.step_results,
            connector_contexts=workflow.connector_contexts,
            blocks=(block,),
            source_path=workflow.source_path,
            launch_dir=workflow.launch_dir,
        ),
        connector_provider=connector_provider,
        active_overrides=active_overrides,
    )
    if not resolution.ok or not resolution.blocks or not isinstance(resolution.blocks[0], ResolvedGuardBlock):
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.RESOLUTION_ERROR,
            diagnostics=resolution.diagnostics,
            plan=ExecutionPlan(
                guard_checks=tuple(_initial_guard_references(workflow)),
                step_names=tuple(_all_step_names(workflow)),
                blockers=(),
            ),
            outputs={
                **_base_verdict_outputs(can_execute=False, allowed_state="blocked", analysis_complete=True),
                "blockers": [],
                "checked_guards": list(_initial_guard_references(workflow)),
                **_guard_coverage_outputs(workflow, checked_guards=list(_initial_guard_references(workflow)), blockers=[]),
                "block_items": _build_pending_block_items(workflow, blocked=False),
            },
        )
    return ResolvedGuardBlock(block_index=block_index, guards=resolution.blocks[0].guards)


def _classify_run_step_block_for_check(block: StepBlock, workflow: Workflow, *, block_index: int) -> list[tuple[Step, CheckRunExpansionDecision]] | None:
    decisions: list[tuple[Step, CheckRunExpansionDecision]] = []
    if not block.steps:
        return None
    for step_index, step in enumerate(block.steps):
        if step.if_ is not None or step.run is None:
            return None
        decision = classify_run_for_check(step, workflow, block_index=block_index, step_index=step_index)
        if not decision.admissible:
            return None
        decisions.append((step, decision))
    return decisions


def _resolve_step_block(
    workflow: Workflow,
    *,
    block_index: int,
    connector_provider: ConnectorProvider | None,
    active_overrides,
) -> ResolvedStepBlock | RuntimeResult:
    block = workflow.blocks[block_index]
    assert isinstance(block, StepBlock)
    resolution = resolve_workflow_references(
        Workflow(
            version=workflow.version,
            workflow=workflow.workflow,
            inputs=workflow.inputs,
            declared_inputs=workflow.declared_inputs,
            explicit_input_keys=workflow.explicit_input_keys,
            let_bindings=workflow.let_bindings,
            state_needs=workflow.state_needs,
            state_bindings=workflow.state_bindings,
            states=workflow.states,
            step_results=workflow.step_results,
            connector_contexts=workflow.connector_contexts,
            blocks=(block,),
            source_path=workflow.source_path,
            launch_dir=workflow.launch_dir,
        ),
        connector_provider=connector_provider,
        active_overrides=active_overrides,
    )
    if not resolution.ok or not resolution.blocks or not isinstance(resolution.blocks[0], ResolvedStepBlock):
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.RESOLUTION_ERROR,
            diagnostics=resolution.diagnostics,
            plan=ExecutionPlan(
                guard_checks=tuple(_initial_guard_references(workflow)),
                step_names=tuple(_all_step_names(workflow)),
                blockers=(),
            ),
            outputs={
                **_base_verdict_outputs(can_execute=False, allowed_state="blocked", analysis_complete=True),
                "blockers": [],
                "checked_guards": list(_initial_guard_references(workflow)),
                **_guard_coverage_outputs(workflow, checked_guards=list(_initial_guard_references(workflow)), blockers=[]),
                "block_items": _build_pending_block_items(workflow, blocked=False),
            },
        )
    return ResolvedStepBlock(block_index=block_index, steps=resolution.blocks[0].steps)


def _interpret_step_block_for_check(
    block: StepBlock,
    workflow: Workflow,
    *,
    block_index: int,
    current_profile_name: str | None,
    current_profile: Profile | None,
    connector_provider: ConnectorProvider | None,
    probe: GuardProbe,
    active_overrides,
    available_profiles: dict[str, Profile] | None,
    profile_working_directories: dict[str, Path | None] | None,
    current_working_directory: Path | None,
    observed_probe_calls: list[dict[str, object]],
) -> dict[str, object] | None:
    resolved_block = _resolve_step_block(
        workflow,
        block_index=block_index,
        connector_provider=connector_provider,
        active_overrides=active_overrides,
    )
    if isinstance(resolved_block, RuntimeResult):
        return {"resolution_error": resolved_block}

    diagnostics: list[Diagnostic] = []
    interpreted_steps: list[str] = []
    skipped_steps: list[str] = []
    incomplete_reasons: list[str] = []
    halt_item: dict[str, object] | None = None
    resume_after_halt = False
    step_items: list[dict[str, object]] = []
    effective_workflow = workflow
    effective_profile_name = current_profile_name
    effective_profile = current_profile
    effective_overrides = active_overrides
    effective_working_directory = current_working_directory
    observation_session = _build_preflight_observation_session(workflow, probe=probe, connector_provider=connector_provider)
    known_observations = [dict(item) for item in observed_probe_calls if isinstance(item, dict)]

    for step_index, (step, resolved_step) in enumerate(zip(block.steps, resolved_block.steps, strict=False)):
        with _checking_working_directory(effective_working_directory):
            condition = evaluate_preflight_step_condition(
                step,
                effective_workflow,
                step_results=effective_workflow.step_results,
                observation_session=observation_session,
            )
        if isinstance(condition, ValueResolutionError):
            halt = build_preflight_halt(
                "condition_not_computable",
                step=step,
                branch_condition=step.if_,
                details={"block_index": block_index, "step_index": step_index},
            )
            diagnostics.append(condition.to_diagnostic(path=("blocks", str(block_index), "steps", str(step_index), "if")))
            incomplete_reasons.append(halt.reason)
            halt_item = halt.to_contract()
            step_items.append(
                _structural_step_item(
                    block_index=block_index,
                    step_index=step_index,
                    step=step,
                    resolved_step=resolved_step,
                    status="halted",
                    condition_status="unknown",
                    halt_reason=halt.reason,
                    preflight_support=_build_preflight_support(
                        resolved_step,
                        action_call=_action_call_from_resolved_operation(resolved_step) if isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "action" else None,
                        known_observations=known_observations,
                    ),
                )
            )
            _append_structural_tail_items(
                block_index=block_index,
                start_step_index=step_index + 1,
                block=block,
                resolved_block=resolved_block,
                step_items=step_items,
                known_observations=known_observations,
            )
            break
        if condition is None:
            halt = build_preflight_halt(
                "condition_not_boolean",
                step=step,
                branch_condition=step.if_,
                details={"block_index": block_index, "step_index": step_index},
            )
            diagnostics.append(
                Diagnostic(
                    code="runtime.step.if.result_type",
                    level="error",
                    message="Step condition must evaluate to a boolean value",
                    path=("blocks", str(block_index), "steps", str(step_index), "if"),
                    details={"actual_type": type(condition).__name__},
                )
            )
            incomplete_reasons.append(halt.reason)
            halt_item = halt.to_contract()
            step_items.append(
                _structural_step_item(
                    block_index=block_index,
                    step_index=step_index,
                    step=step,
                    resolved_step=resolved_step,
                    status="halted",
                    condition_status="unknown",
                    halt_reason=halt.reason,
                    preflight_support=_build_preflight_support(
                        resolved_step,
                        action_call=_action_call_from_resolved_operation(resolved_step) if isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "action" else None,
                        known_observations=known_observations,
                    ),
                )
            )
            _append_structural_tail_items(
                block_index=block_index,
                start_step_index=step_index + 1,
                block=block,
                resolved_block=resolved_block,
                step_items=step_items,
                known_observations=known_observations,
            )
            break
        if condition is False:
            skipped_steps.append(step.name)
            step_observations = [_observed_probe_call_from_resolved_operation(resolved_step)] if isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "probe" else []
            step_items.append(
                {
                    "block_index": block_index,
                    "step_index": step_index,
                    "name": step.name,
                    "reference": resolved_step.reference,
                    "preflight_classification": classify_preflight_step(step, resolved_step),
                    "status": "skipped",
                    "conditional": step.if_ is not None,
                    "condition": step.if_,
                    "condition_status": "false",
                    "observations": step_observations,
                    "action_call": _action_call_from_resolved_operation(resolved_step) if isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "action" else None,
                }
            )
            known_observations.extend(step_observations)
            continue

        classification = classify_preflight_step(step, resolved_step)
        if classification == "context_only" and step.profile_switch is not None:
            transition = _apply_static_profile_switch_block(
                StepBlock(steps=(step,)),
                workflow=effective_workflow,
                available_profiles=available_profiles,
            )
            if transition is None:
                halt = build_preflight_halt(
                    "profile_switch_not_resolvable_from_current_knowledge",
                    step=step,
                    details={"block_index": block_index, "step_index": step_index},
                )
                incomplete_reasons.append(halt.reason)
                halt_item = halt.to_contract()
                step_items.append(
                    {
                        "block_index": block_index,
                        "step_index": step_index,
                        "name": step.name,
                        "reference": resolved_step.reference,
                        "preflight_classification": classification,
                        "status": "halted",
                        "conditional": step.if_ is not None,
                        "condition": step.if_,
                        "condition_status": "true" if step.if_ is not None else None,
                        "halt_reason": halt.reason,
                    }
                )
                break
            effective_profile_name, effective_profile, effective_overrides, effective_workflow = transition
            effective_working_directory = (
                None
                if effective_profile_name is None or profile_working_directories is None
                else profile_working_directories.get(effective_profile_name)
            )
            interpreted_steps.append(step.name)
            step_items.append(
                {
                    "block_index": block_index,
                    "step_index": step_index,
                    "name": step.name,
                    "reference": resolved_step.reference,
                    "preflight_classification": classification,
                    "status": "interpreted",
                    "conditional": step.if_ is not None,
                    "condition": step.if_,
                    "condition_status": "true" if step.if_ is not None else None,
                    "active_profile": effective_profile_name,
                }
            )
            continue
        if classification == "read_only_analyzable":
            with _checking_working_directory(effective_working_directory):
                result = _evaluate_analyzable_preflight_step(
                    step,
                    resolved_step,
                    effective_workflow,
                    probe=probe,
                    observation_session=observation_session,
                )
            diagnostics.extend(result.diagnostics)
            if result.status != "ok":
                halt = build_preflight_halt(
                    "read_only_step_failed",
                    step=step,
                    details={"block_index": block_index, "step_index": step_index, "status": result.status},
                )
                incomplete_reasons.append(halt.reason)
                halt_item = halt.to_contract()
                step_items.append(
                    {
                        "block_index": block_index,
                        "step_index": step_index,
                        "name": step.name,
                        "reference": resolved_step.reference,
                        "preflight_classification": classification,
                        "status": "halted",
                        "conditional": step.if_ is not None,
                        "condition": step.if_,
                        "condition_status": "true" if step.if_ is not None else None,
                        "halt_reason": halt.reason,
                        "operation_status": result.status,
                    }
                )
                _append_structural_tail_items(
                    block_index=block_index,
                    start_step_index=step_index + 1,
                    block=block,
                    resolved_block=resolved_block,
                    step_items=step_items,
                    known_observations=known_observations,
                )
                break
            if step.register is not None:
                store_preflight_register_output(step.register, result, step_results=effective_workflow.step_results)
            interpreted_steps.append(step.name)
            step_observations = [_observed_probe_call_from_resolved_operation(resolved_step)] if isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "probe" else []
            step_items.append(
                {
                    "block_index": block_index,
                    "step_index": step_index,
                    "name": step.name,
                    "reference": resolved_step.reference,
                    "preflight_classification": classification,
                    "status": "interpreted",
                    "conditional": step.if_ is not None,
                    "condition": step.if_,
                    "condition_status": "true" if step.if_ is not None else None,
                    "register": step.register,
                    "operation_status": result.status,
                    "summary": result.summary,
                    "outputs": dict(result.outputs),
                    "observation_scopes": [resolved_step.reference] if isinstance(resolved_step, ResolvedOperation) else [],
                    "observations": step_observations,
                    "action_call": _action_call_from_resolved_operation(resolved_step) if isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "action" else None,
                }
            )
            known_observations.extend(step_observations)
            continue

        action_call = _action_call_from_resolved_operation(resolved_step) if isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "action" else None
        preflight_support = _build_preflight_support(resolved_step, action_call=action_call, known_observations=known_observations)
        halt = build_preflight_halt(
            "effectful_step_encountered" if classification == "effectful" else "preflight_step_not_analyzable",
            step=step,
            details={
                "block_index": block_index,
                "step_index": step_index,
                "classification": classification,
                "reference": resolved_step.reference,
            },
        )
        incomplete_reasons.append(halt.reason)
        halt_item = halt.to_contract()
        step_items.append(
            {
                "block_index": block_index,
                "step_index": step_index,
                "name": step.name,
                "reference": resolved_step.reference,
                "preflight_classification": classification,
                "status": "halted",
                "conditional": step.if_ is not None,
                "condition": step.if_,
                "condition_status": "true" if step.if_ is not None else None,
                "halt_reason": halt.reason,
                "observations": [_observed_probe_call_from_resolved_operation(resolved_step)] if isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "probe" else [],
                "action_call": action_call,
                "preflight_support": preflight_support,
            }
        )
        trailing_profile_switches = tuple(block.steps[step_index + 1 :])
        if trailing_profile_switches and all(candidate.profile_switch is not None and candidate.if_ is None for candidate in trailing_profile_switches):
            trailing_transition = _apply_static_profile_switch_block(
                StepBlock(steps=trailing_profile_switches),
                workflow=effective_workflow,
                available_profiles=available_profiles,
            )
            if trailing_transition is not None:
                resume_after_halt = True
                effective_profile_name, effective_profile, effective_overrides, effective_workflow = trailing_transition
                effective_working_directory = (
                    None
                    if effective_profile_name is None or profile_working_directories is None
                    else profile_working_directories.get(effective_profile_name)
                )
                for trailing_index, trailing_step in enumerate(trailing_profile_switches, start=step_index + 1):
                    interpreted_steps.append(trailing_step.name)
                    step_items.append(
                        {
                            "block_index": block_index,
                            "step_index": trailing_index,
                            "name": trailing_step.name,
                            "reference": "profile_switch",
                            "preflight_classification": "context_only",
                            "status": "interpreted",
                            "conditional": False,
                            "condition": None,
                            "condition_status": None,
                            "active_profile": effective_profile_name,
                        }
                    )
        break

    if not interpreted_steps and not skipped_steps and halt_item is None:
        return None

    return {
        "diagnostics": diagnostics,
        "incomplete_reasons": incomplete_reasons,
        "halted": halt_item is not None and not resume_after_halt,
        "step_items": step_items,
        "halts": [] if halt_item is None else [halt_item],
        "workflow": effective_workflow,
        "current_profile_name": effective_profile_name,
        "current_profile": effective_profile,
        "active_overrides": effective_overrides,
        "current_working_directory": effective_working_directory,
        "block_item": {
            "block_index": block_index,
            "type": "steps",
            "status": "preflight_halted" if halt_item is not None else "preflight_interpreted",
            "step_names": [step.name for step in block.steps],
            "conditional_steps": [step.name for step in block.steps if step.if_ is not None],
            "interpreted_steps": interpreted_steps,
            "skipped_steps": skipped_steps,
            "active_profile": effective_profile_name,
            "preflight_halt": halt_item,
        },
    }


def _evaluate_analyzable_preflight_step(
    step: Step,
    resolved_step: ResolvedStep,
    workflow: Workflow,
    *,
    probe: GuardProbe,
    observation_session: ReadOnlyObservationSession,
) -> OperationResult:
    if isinstance(resolved_step, ResolvedOperation):
        return evaluate_preflight_probe_step(step, resolved_step, workflow, guard_probe=probe)
    if isinstance(resolved_step, ResolvedBuiltinStep) and resolved_step.builtin == "value":
        return evaluate_preflight_value_step(step, workflow, step_results=workflow.step_results, observation_session=observation_session)
    return OperationResult(status="state_error", summary=f"Step '{step.name}' is not a supported preflight step")


def _expand_run_step_block_for_check(
    expansions: list[tuple[Step, CheckRunExpansionDecision]],
    *,
    current_workflow: Workflow,
    current_profile_name: str | None,
    current_profile: Profile | None,
    active_overrides,
    available_profiles: dict[str, Profile] | None,
    profile_working_directories: dict[str, Path | None] | None,
    connector_provider: ConnectorProvider | None,
) -> dict[str, object]:
    diagnostics: list[Diagnostic] = []
    operation_results: list[OperationResult] = []
    checked_guards: list[str] = []
    guard_details: list[dict[str, object]] = []
    block_items: list[dict[str, object]] = []
    blockers: list[str] = []
    incomplete_reasons: list[str] = []
    failed_guard: str | None = None
    halted = False
    effective_workflow = current_workflow
    current_overrides = active_overrides
    effective_profile_name = current_profile_name
    effective_profile = current_profile
    effective_working_directory = (
        None
        if effective_profile_name is None or profile_working_directories is None
        else profile_working_directories.get(effective_profile_name)
    )
    for step, decision in expansions:
        if decision.workflow is None:
            halted = True
            incomplete_reasons.append("run_expansion_missing_workflow")
            break
        result = check_workflow(
            decision.workflow,
            profile=effective_profile,
            available_profiles=available_profiles,
            profile_working_directories=profile_working_directories,
            connector_provider=connector_provider,
        )
        diagnostics.extend(result.diagnostics)
        operation_results.extend(result.operation_results)
        checked_guards.extend(cast(list[str], result.outputs.get("checked_guards", [])))
        guard_details.extend(cast(list[dict[str, object]], result.outputs.get("guard_details", [])))
        blockers.extend(cast(list[str], result.outputs.get("blockers", [])))
        for item in result.outputs.get("block_items", []):
            if not isinstance(item, dict):
                continue
            nested = dict(item)
            nested["expanded_from_step"] = step.name
            nested["expanded_from_run"] = step.run
            block_items.append(nested)
        if result.failed_guard is not None and failed_guard is None:
            failed_guard = result.failed_guard
        if result.status is RuntimeStatus.GUARD_FAILED:
            halted = True
            break
        if result.outputs.get("allowed_state") != "allowed":
            halted = True
            incomplete_reasons.extend(reason for reason in result.outputs.get("incomplete_reasons", []) if isinstance(reason, str))
            break
        next_profile_name = result.outputs.get("active_profile")
        if isinstance(next_profile_name, str) and available_profiles is not None and next_profile_name in available_profiles:
            effective_profile_name = next_profile_name
            effective_profile = available_profiles[next_profile_name]
            current_overrides = effective_profile.overrides
            applied = apply_profile_defaults_to_subsequent_steps(effective_workflow, effective_profile)
            effective_workflow = effective_workflow if applied.workflow is None else applied.workflow
            effective_working_directory = (
                None
                if profile_working_directories is None
                else profile_working_directories.get(next_profile_name)
            )
    return {
        "diagnostics": diagnostics,
        "operation_results": operation_results,
        "checked_guards": checked_guards,
        "guard_details": guard_details,
        "block_items": block_items,
        "blockers": blockers,
        "incomplete_reasons": incomplete_reasons,
        "failed_guard": failed_guard,
        "halted": halted,
        "workflow": effective_workflow,
        "current_profile_name": effective_profile_name,
        "current_profile": effective_profile,
        "active_overrides": current_overrides,
        "current_working_directory": effective_working_directory,
    }


def _is_static_profile_switch_block(block: StepBlock) -> bool:
    return bool(block.steps) and all(step.profile_switch is not None for step in block.steps)


def _apply_static_profile_switch_block(
    block: StepBlock,
    *,
    workflow: Workflow,
    available_profiles: dict[str, Profile] | None,
) -> tuple[str, Profile, tuple, Workflow] | None:
    current_workflow = workflow
    current_profile_name: str | None = None
    current_profile: Profile | None = None
    current_overrides = ()
    for step in block.steps:
        if step.profile_switch is None or step.if_ is not None:
            return None
        try:
            profile_name = resolve_runtime_value(step.profile_switch, current_workflow)
        except ValueResolutionError:
            return None
        if not isinstance(profile_name, str) or not profile_name or available_profiles is None or profile_name not in available_profiles:
            return None
        current_profile = available_profiles[profile_name]
        current_profile_name = profile_name
        applied = apply_profile_defaults_to_subsequent_steps(current_workflow, current_profile)
        current_workflow = current_workflow if applied.workflow is None else applied.workflow
        current_overrides = current_profile.overrides
    if current_profile_name is None or current_profile is None:
        return None
    return current_profile_name, current_profile, current_overrides, current_workflow


@contextlib.contextmanager
def _checking_working_directory(target: Path | None):
    if target is None:
        yield
        return

    previous = Path.cwd()
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(previous)


def _build_pending_block_items(workflow: Workflow, *, blocked: bool, start_index: int = 0, active_profile: str | None = None) -> list[dict[str, object]]:
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
                    "active_profile": active_profile,
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
                    "active_profile": active_profile,
                }
            )
    return items


def _pending_guard_block_item_from_declared(block_index: int, declared: GuardBlock, active_profile: str | None) -> dict[str, object]:
    return {
        "block_index": block_index,
        "type": "guards",
        "status": "pending",
        "guard_references": [guard.reference for guard in declared.guards],
        "blockers": [],
        "guard_details": [],
        "active_profile": active_profile,
    }


def _pending_step_block_item_from_declared(block_index: int, declared: StepBlock, *, blocked: bool, active_profile: str | None) -> dict[str, object]:
    return {
        "block_index": block_index,
        "type": "steps",
        "status": "blocked" if blocked else "pending",
        "step_names": [step.name for step in declared.steps],
        "conditional_steps": [step.name for step in declared.steps if step.if_ is not None],
        "active_profile": active_profile,
    }


def _has_later_guard_block(workflow: Workflow, *, block_index: int) -> bool:
    return any(isinstance(block, GuardBlock) for block in workflow.blocks[block_index + 1 :])


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


def _build_observation_basis_outputs(
    workflow: Workflow,
    resolution,
    guard_details: list[dict[str, object]],
) -> dict[str, object]:
    used_scopes = sorted(
        {
            scope
            for detail in guard_details
            if isinstance(detail, dict)
            for scope in detail.get("observation_scopes", [])
            if isinstance(scope, str)
        }
    )
    invalidation_scopes = sorted(_collect_potential_invalidation_scopes(workflow, resolution))
    weakened_scopes = sorted(
        {
            scope
            for scope in used_scopes
            if any(_scope_invalidated(scope, invalidation) for invalidation in invalidation_scopes)
        }
    )
    return {
        "used_observation_scopes": used_scopes,
        "potential_invalidation_scopes": invalidation_scopes,
        "weakened_observation_scopes": weakened_scopes,
        "verdict_basis_weakened": False,
    }


def _normalize_authored_value(value: JSONValue) -> JSONValue:
    if isinstance(value, str):
        expression = extract_embedded_local_expression(value)
        if expression is not None:
            return {"expression": expression}
        return value
    if isinstance(value, list):
        return [_normalize_authored_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_authored_value(item) for key, item in value.items()}
    return value


def _normalize_expression_node(node: ValueExpressionNode, *, source: str) -> JSONValue:
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, ListNode):
        return [_normalize_expression_node(item, source=source) for item in node.items]
    if isinstance(node, ObjectEntryNode):
        return _normalize_expression_node(node.value, source=source)
    if isinstance(node, ObjectNode):
        return {entry.key: _normalize_expression_node(entry.value, source=source) for entry in node.entries}
    return {"expression": render_expression_text(node, source=source)}


def _observed_probe_call_from_resolved_operation(resolved: ResolvedOperation) -> dict[str, object]:
    return {
        "probe": resolved.reference,
        "with": {name: _normalize_authored_value(value) for name, value in (resolved.declared_with or {}).items()},
        "fields": [],
    }


def _observed_probe_call_from_expression_probe(probe: ResolvedExpressionProbe, *, source: str) -> dict[str, object]:
    return {
        "probe": probe.reference,
        "with": {name: _normalize_expression_node(value, source=source) for name, value in probe.arguments},
        "fields": list(probe.fields),
    }


def _action_call_from_resolved_operation(resolved: ResolvedOperation) -> dict[str, object]:
    return {
        "reference": resolved.reference,
        "with": {name: _normalize_authored_value(value) for name, value in (resolved.declared_with or {}).items()},
    }


def _structural_step_item(
    *,
    block_index: int,
    step_index: int,
    step: Step,
    resolved_step: ResolvedStep,
    status: str,
    condition_status: str | None,
    halt_reason: str | None = None,
    preflight_support: dict[str, object] | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "block_index": block_index,
        "step_index": step_index,
        "name": step.name,
        "reference": resolved_step.reference,
        "preflight_classification": classify_preflight_step(step, resolved_step),
        "status": status,
        "conditional": step.if_ is not None,
        "condition": step.if_,
        "condition_status": condition_status,
        "action_call": _action_call_from_resolved_operation(resolved_step) if isinstance(resolved_step, ResolvedOperation) and resolved_step.operation.kind == "action" else None,
    }
    if isinstance(resolved_step, ResolvedRunStep):
        item["body_kind"] = resolved_step.body_kind
        if step.for_each is not None:
            item["fan_out"] = {"enabled": True}
    if halt_reason is not None:
        item["halt_reason"] = halt_reason
    if preflight_support is not None:
        item["preflight_support"] = preflight_support
    return item


def _append_structural_tail_items(
    *,
    block_index: int,
    start_step_index: int,
    block: StepBlock,
    resolved_block: ResolvedStepBlock,
    step_items: list[dict[str, object]],
    known_observations: list[dict[str, object]],
) -> None:
    for tail_step_index in range(start_step_index, min(len(block.steps), len(resolved_block.steps))):
        tail_step = block.steps[tail_step_index]
        tail_resolved = resolved_block.steps[tail_step_index]
        action_call = _action_call_from_resolved_operation(tail_resolved) if isinstance(tail_resolved, ResolvedOperation) and tail_resolved.operation.kind == "action" else None
        preflight_support = _build_preflight_support(tail_resolved, action_call=action_call, known_observations=known_observations)
        step_items.append(
            _structural_step_item(
                block_index=block_index,
                step_index=tail_step_index,
                step=tail_step,
                resolved_step=tail_resolved,
                status="pending",
                condition_status="unknown" if tail_step.if_ is not None else None,
                preflight_support=preflight_support,
            )
        )


def _append_structural_items_for_uninterpreted_step_blocks(
    *,
    workflow: Workflow,
    block_items: list[dict[str, object]],
    preflight_step_items: list[dict[str, object]],
    connector_provider: ConnectorProvider | None,
    active_overrides,
    observed_probe_calls: list[dict[str, object]],
) -> RuntimeResult | None:
    existing_block_indexes = {
        item.get("block_index")
        for item in preflight_step_items
        if isinstance(item, dict) and isinstance(item.get("block_index"), int)
    }
    step_block_items = {
        item.get("block_index"): item
        for item in block_items
        if isinstance(item, dict) and item.get("type") == "steps" and isinstance(item.get("block_index"), int)
    }
    for block_index, declared_block in enumerate(workflow.blocks):
        if not isinstance(declared_block, StepBlock):
            continue
        if block_index in existing_block_indexes:
            continue
        block_item = step_block_items.get(block_index)
        if not isinstance(block_item, dict):
            continue
        resolved_block = _resolve_step_block(
            workflow,
            block_index=block_index,
            connector_provider=connector_provider,
            active_overrides=active_overrides,
        )
        if isinstance(resolved_block, RuntimeResult):
            return resolved_block
        known_observations = [dict(item) for item in observed_probe_calls if isinstance(item, dict)]
        _append_structural_tail_items(
            block_index=block_index,
            start_step_index=0,
            block=declared_block,
            resolved_block=resolved_block,
            step_items=preflight_step_items,
            known_observations=known_observations,
        )
    return None


def _render_preflight_observation(template, *, action_call: dict[str, object] | None) -> dict[str, object]:
    rendered_with: dict[str, object] = {}
    template_with = template.with_
    action_inputs = {} if action_call is None else action_call.get("with", {})
    if not isinstance(action_inputs, dict):
        action_inputs = {}
    for name, value in template_with.items():
        if isinstance(value, str):
            match = _ACTION_PLACEHOLDER_PATTERN.fullmatch(value)
            if match is not None:
                rendered_with[name] = action_inputs.get(match.group(1), value)
                continue
        rendered_with[name] = _normalize_authored_value(value)
    return {
        "probe": template.probe,
        "with": rendered_with,
        "fields": list(template.fields),
    }


def _canonical_observation_key(observation: dict[str, object]) -> str:
    import json

    return json.dumps(observation, sort_keys=True, separators=(",", ":"))


def _build_preflight_support(
    resolved_step: ResolvedStep,
    *,
    action_call: dict[str, object] | None,
    known_observations: list[dict[str, object]],
) -> dict[str, object] | None:
    if not isinstance(resolved_step, ResolvedOperation) or resolved_step.operation.kind != "action":
        return None
    templates = list(resolved_step.operation.preflight_observations)
    if not templates:
        return {
            "strength": "not_applicable",
            "recommended_observations": [],
            "matched_observations": [],
            "missing_observations": [],
        }
    recommended = [_render_preflight_observation(template, action_call=action_call) for template in templates]
    known_keys = {_canonical_observation_key(item) for item in known_observations}
    matched = [item for item in recommended if _canonical_observation_key(item) in known_keys]
    missing = [item for item in recommended if _canonical_observation_key(item) not in known_keys]
    strength = "strong" if len(matched) == len(recommended) else "weak" if not matched else "partial"
    return {
        "strength": strength,
        "recommended_observations": recommended,
        "matched_observations": matched,
        "missing_observations": missing,
    }


def _collect_potential_invalidation_scopes(workflow: Workflow, resolution) -> set[str]:
    scopes: set[str] = set()
    for block in resolution.blocks:
        if not isinstance(block, ResolvedStepBlock):
            continue
        declared = workflow.blocks[block.block_index]
        assert isinstance(declared, StepBlock)
        for step, resolved_step in zip(declared.steps, block.steps, strict=False):
            if not isinstance(resolved_step, ResolvedOperation) or resolved_step.operation.kind != "action":
                continue
            invalidation = resolved_step.operation.invalidates_observations or (f"{resolved_step.connector_namespace}.*",)
            scopes.update(scope for scope in invalidation if isinstance(scope, str))
    return scopes


def _scope_invalidated(scope: str, invalidation: str) -> bool:
    if invalidation.endswith(".*"):
        prefix = invalidation[:-2]
        return scope == prefix or scope.startswith(f"{prefix}.")
    return scope == invalidation


def _default_guard_probe(*, provider: ConnectorProvider | None):
    """Default side-effect-free probe backed by canonical connector operations."""

    def evaluate(resolved_guard: ResolvedOperation | ResolvedExpressionProbe, workflow: Workflow) -> OperationResult:
        resolved_provider = provider or get_default_connector_provider()
        return resolved_provider.guard_probe(resolved_guard, workflow)

    return evaluate


def _build_preflight_observation_session(
    workflow: Workflow,
    *,
    probe: GuardProbe,
    connector_provider: ConnectorProvider | None,
) -> ReadOnlyObservationSession:
    resolved_provider = connector_provider or get_default_connector_provider()

    def observe(request: ConditionObservationRequest) -> ConditionObservationResult:
        reference = ".".join(request.target)
        operation = resolved_provider.registry.get_operation(reference)
        if operation is None:
            return ConditionObservationResult(
                status="probe_failed",
                value=None,
                diagnostics=(
                    Diagnostic(
                        code="runtime.local_expression.call_target_unknown",
                        level="error",
                        message=f"Read-only call target '{reference}' is not a known public operation",
                        path=(),
                        details={"reference": reference},
                    ),
                ),
                reference=reference,
            )
        if operation.kind != "probe":
            return ConditionObservationResult(
                status="probe_failed",
                value=None,
                diagnostics=(
                    Diagnostic(
                        code="runtime.local_expression.call_target_not_read_only",
                        level="error",
                        message=f"Read-only expression calls require a probe target, got '{reference}'",
                        path=(),
                        details={"reference": reference, "kind": operation.kind},
                    ),
                ),
                reference=reference,
            )
        result = probe(
            ResolvedOperation(
                reference=reference,
                connector_namespace=request.target[0],
                operation=operation,
                source="public",
                declared_with={name: value for name, value in request.arguments},
            ),
            workflow,
        )
        if result.status != "ok":
            return ConditionObservationResult(status="probe_failed", value=None, diagnostics=result.diagnostics, reference=reference)
        value = _extract_probe_value(result.outputs, request.fields)
        if value is _MISSING:
            return ConditionObservationResult(
                status="probe_failed",
                value=None,
                diagnostics=(
                    Diagnostic(
                        code="runtime.local_expression.probe_field_missing",
                        level="error",
                        message=f"Probe field path '{'.'.join(request.fields)}' was not present at runtime",
                        path=(),
                        details={"reference": reference, "field_path": ".".join(request.fields)},
                    ),
                ),
                reference=reference,
            )
        return ConditionObservationResult(status="ok", value=value, diagnostics=result.diagnostics, reference=reference)

    return ReadOnlyObservationSession(observe)


def _evaluate_guard_expression(
    resolved_guard: ResolvedConditionExpression,
    workflow: Workflow,
    probe: GuardProbe,
) -> OperationResult:
    observer = _ResolvedGuardObserver(resolved_guard=resolved_guard, workflow=workflow, probe=probe)
    evaluation = evaluate_condition_expression(
        resolved_guard.parsed,
        workflow,
        observe=observer.observe,
    )
    return _build_guard_expression_result(resolved_guard.expr, evaluation)


@dataclass(slots=True)
class _ResolvedGuardObserver:
    resolved_guard: ResolvedConditionExpression
    workflow: Workflow
    probe: GuardProbe
    _probes_by_expression: dict[str, ResolvedExpressionProbe] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._probes_by_expression = {probe.expression_text: probe for probe in self.resolved_guard.probes}

    def observe(self, request: ConditionObservationRequest) -> ConditionObservationResult:
        probe_spec = self._probes_by_expression.get(request.expression_text)
        if probe_spec is None:
            raise ValueError(
                f"Resolved probe metadata missing for expression segment: {request.expression_text} ({request.fields})"
            )
        runtime_probe_spec = ResolvedExpressionProbe(
            reference=probe_spec.reference,
            connector_namespace=probe_spec.connector_namespace,
            operation=probe_spec.operation,
            source=probe_spec.source,
            expression_text=probe_spec.expression_text,
            fields=probe_spec.fields,
            arguments=tuple((name, _json_value_to_expression_node(value)) for name, value in request.arguments),
        )
        result = self.probe(runtime_probe_spec, self.workflow)
        if result.status != "ok":
            return ConditionObservationResult(status="probe_failed", value=None, diagnostics=result.diagnostics, reference=probe_spec.reference)

        value = _extract_probe_value(result.outputs, probe_spec.fields)
        if value is _MISSING:
            diagnostic = Diagnostic(
                code="guard.probe_field_missing",
                level="error",
                message=f"Probe field path '{'.'.join(probe_spec.fields)}' was not present at runtime",
                path=(),
                details={"reference": probe_spec.reference, "field_path": ".".join(probe_spec.fields)},
            )
            return ConditionObservationResult(
                status="probe_failed",
                value=None,
                diagnostics=result.diagnostics + (diagnostic,),
                reference=probe_spec.reference,
            )

        return ConditionObservationResult(status="ok", value=value, diagnostics=result.diagnostics, reference=probe_spec.reference)


def _json_value_to_expression_node(value: JSONValue) -> ValueExpressionNode:
    if isinstance(value, list):
        return ListNode(start=0, end=0, items=tuple(_json_value_to_expression_node(item) for item in value))
    if isinstance(value, dict):
        return ObjectNode(
            start=0,
            end=0,
            entries=tuple(
                ObjectEntryNode(start=0, end=0, key=key, value=_json_value_to_expression_node(item))
                for key, item in value.items()
            ),
        )
    return LiteralNode(start=0, end=0, value=value)


def _build_guard_expression_result(expr: str, evaluation: ConditionEvaluationResult) -> OperationResult:
    failed_trace = next(
        (entry for entry in reversed(evaluation.trace) if entry.status == "probe_failed" or entry.value is False),
        None,
    )
    if evaluation.status == "probe_failed":
        return OperationResult(
            status="probe_failed",
            summary="Guard expression could not be evaluated safely",
            diagnostics=evaluation.diagnostics,
            outputs={"guard": expr, "result": None, "failed_subcondition": None if failed_trace is None else failed_trace.expr},
            raw={"cache_entries": evaluation.cache_entries, "trace": [item.to_contract() for item in evaluation.trace], "failure_kind": "probe_failed"},
        )
    if not isinstance(evaluation.value, bool):
        diagnostic = Diagnostic(
            code="runtime.guard.result_type",
            level="error",
            message="Guard expression must evaluate to a boolean value",
            path=(),
            details={"guard": expr, "actual_type": type(evaluation.value).__name__},
        )
        return OperationResult(
            status="execution_error",
            summary="Guard expression produced a non-boolean result",
            diagnostics=evaluation.diagnostics + (diagnostic,),
            outputs={"guard": expr, "result": None, "failed_subcondition": expr},
            raw={"cache_entries": evaluation.cache_entries, "trace": [item.to_contract() for item in evaluation.trace], "failure_kind": "result_type"},
        )
    passed = evaluation.value
    return OperationResult(
        status="ok" if passed else "guard_failed",
        summary="Guard expression evaluated successfully" if passed else "Guard expression evaluated false",
        diagnostics=evaluation.diagnostics,
        outputs={"guard": expr, "result": passed, "failed_subcondition": None if passed or failed_trace is None else failed_trace.expr},
        raw={"cache_entries": evaluation.cache_entries, "trace": [item.to_contract() for item in evaluation.trace], "failure_kind": "guard_failed" if not passed else None},
    )


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


def _guard_observation_scopes(resolved_guard: ResolvedOperation | ResolvedConditionExpression) -> list[str]:
    if isinstance(resolved_guard, ResolvedOperation):
        return [resolved_guard.reference]
    if isinstance(resolved_guard, ResolvedConditionExpression):
        return [probe.reference for probe in resolved_guard.probes]
    return []


def _guard_observations(resolved_guard: ResolvedOperation | ResolvedConditionExpression) -> list[dict[str, object]]:
    if isinstance(resolved_guard, ResolvedOperation):
        return [_observed_probe_call_from_resolved_operation(resolved_guard)]
    if isinstance(resolved_guard, ResolvedConditionExpression):
        return [_observed_probe_call_from_expression_probe(probe, source=resolved_guard.expr) for probe in resolved_guard.probes]
    return []


def _build_guard_detail(
    reference: str,
    result: OperationResult,
    *,
    observation_scopes: list[str] | None = None,
    observations: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "reference": reference,
        "status": result.status,
        "summary": result.summary,
        "failed_subcondition": result.outputs.get("failed_subcondition"),
        "failure_kind": result.raw.get("failure_kind"),
        "trace": result.raw.get("trace", []),
        "observation_scopes": [] if observation_scopes is None else list(observation_scopes),
        "observations": [] if observations is None else [dict(item) for item in observations],
    }
