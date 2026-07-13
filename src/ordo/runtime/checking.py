"""Check mode for pre-execution validation, resolution, and guard analysis."""

from __future__ import annotations

from typing import cast

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, PreflightBlockNode, PreflightDecisionModel, PreflightGuardNode, RuntimeResult, RuntimeStatus
from ordo.model.workflow import GuardBlock, Step, StepBlock, Workflow

from .fragment_runs import CheckRunExpansionDecision, classify_run_for_check
from .guard_expressions import BinaryNode, CallNode, GuardExpressionNode, ListNode, LiteralNode, ReferenceNode, StateReferenceNode, UnaryNode
from .state import RuntimeStateError, read_state_document, read_state_value, resolve_state_target
from .launchers import validate_step_launchers
from .profiles import apply_profile_defaults_to_subsequent_steps, apply_profile_to_workflow
from .providers import ConnectorProvider, GuardProbe, get_default_connector_provider
from .resolution import ResolvedExpressionProbe, ResolvedGuardBlock, ResolvedGuardExpression, ResolvedOperation, ResolvedStepBlock, resolve_workflow_references
from .value_resolution import ValueResolutionError, resolve_runtime_value
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

    initial_resolution = resolve_workflow_references(
        effective_workflow,
        connector_provider=connector_provider,
        active_overrides=active_overrides,
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
    for block_index, declared_block in enumerate(effective_workflow.blocks):
        if isinstance(declared_block, GuardBlock):
            if halted:
                block_items.append(_pending_guard_block_item_from_declared(block_index, declared_block, current_profile_name))
                continue
            resolved_block = _resolve_guard_block(
                effective_workflow,
                block_index=block_index,
                connector_provider=connector_provider,
                active_overrides=active_overrides,
            )
            if isinstance(resolved_block, RuntimeResult):
                return resolved_block
            block_blockers: list[str] = []
            block_guard_details: list[dict[str, object]] = []
            for resolved_guard in resolved_block.guards:
                if isinstance(resolved_guard, ResolvedGuardExpression):
                    result = _evaluate_guard_expression(resolved_guard, effective_workflow, probe)
                else:
                    result = probe(resolved_guard, effective_workflow)
                operation_results.append(result)
                diagnostics.extend(result.diagnostics)
                detail = _build_guard_detail(resolved_guard.reference, result, observation_scopes=_guard_observation_scopes(resolved_guard))
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
            if halted:
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
            current_profile_name, current_profile, active_overrides, effective_workflow = transition
            active_profile = current_profile_name
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
                current_profile=current_profile,
                available_profiles=available_profiles,
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
            if expansion_outcome["failed_guard"] is not None and failed_guard is None:
                failed_guard = cast(str, expansion_outcome["failed_guard"])
            if expansion_outcome["halted"]:
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

    if blockers:
        observation_basis = _build_observation_basis_outputs(effective_workflow, initial_resolution, guard_details)
        outputs = {
            **_base_verdict_outputs(can_execute=False, allowed_state="blocked", analysis_complete=True),
            "blockers": blockers,
            "checked_guards": checked_guards,
            **_guard_coverage_outputs(effective_workflow, checked_guards=checked_guards, blockers=blockers),
            **observation_basis,
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
            preflight_decision=_build_preflight_decision_model(effective_workflow, outputs),
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
        **_build_observation_basis_outputs(effective_workflow, initial_resolution, guard_details),
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
        preflight_decision=_build_preflight_decision_model(effective_workflow, outputs),
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
            state_needs=workflow.state_needs,
            state_bindings=workflow.state_bindings,
            states=workflow.states,
            step_results=workflow.step_results,
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


def _expand_run_step_block_for_check(
    expansions: list[tuple[Step, CheckRunExpansionDecision]],
    *,
    current_profile: Profile | None,
    available_profiles: dict[str, Profile] | None,
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
    for step, decision in expansions:
        if decision.workflow is None:
            halted = True
            incomplete_reasons.append("run_expansion_missing_workflow")
            break
        result = check_workflow(
            decision.workflow,
            profile=current_profile,
            available_profiles=available_profiles,
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
        "verdict_basis_weakened": bool(weakened_scopes),
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


def _guard_observation_scopes(resolved_guard: ResolvedOperation | ResolvedGuardExpression) -> list[str]:
    if isinstance(resolved_guard, ResolvedOperation):
        return [resolved_guard.reference]
    if isinstance(resolved_guard, ResolvedGuardExpression):
        return [probe.reference for probe in resolved_guard.probes]
    return []


def _build_guard_detail(reference: str, result: OperationResult, *, observation_scopes: list[str] | None = None) -> dict[str, object]:
    return {
        "reference": reference,
        "status": result.status,
        "summary": result.summary,
        "failed_subcondition": result.outputs.get("failed_subcondition"),
        "failure_kind": result.raw.get("failure_kind"),
        "trace": result.raw.get("trace", []),
        "observation_scopes": [] if observation_scopes is None else list(observation_scopes),
    }
