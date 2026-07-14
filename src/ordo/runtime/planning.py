"""Plan mode for structured pre-execution visibility."""

from __future__ import annotations

from typing import cast

from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import GuardBlock, StepBlock, Workflow

from .checking import check_workflow
from .preflight_steps import classify_preflight_step
from .providers import ConnectorProvider, GuardProbe
from .profiles import apply_profile_to_workflow
from .resolution import ResolvedBuiltinStep, ResolvedGuardBlock, ResolvedGuardExpression, ResolvedRunStep, ResolvedStepBlock, WorkflowResolution, resolve_workflow_references
from .validation import validate_workflow_document


def _condition_status_for_step(step, preflight_item: dict[str, object]) -> str | None:
    if step.if_ is None:
        return None
    status = preflight_item.get("condition_status")
    return cast(str, status) if isinstance(status, str) else "unknown"


def _observation_scopes_for_step(step, resolved_step, preflight_item: dict[str, object]) -> list[str]:
    scopes = preflight_item.get("observation_scopes")
    if isinstance(scopes, list):
        return [scope for scope in scopes if isinstance(scope, str)]
    if hasattr(resolved_step, "operation") and getattr(resolved_step.operation, "kind", None) == "probe":
        return [resolved_step.reference]
    return []


def _invalidates_scopes_for_step(resolved_step) -> list[str]:
    if not hasattr(resolved_step, "operation") or getattr(resolved_step.operation, "kind", None) != "action":
        return []
    invalidation = resolved_step.operation.invalidates_observations or (f"{resolved_step.connector_namespace}.*",)
    return [scope for scope in invalidation if isinstance(scope, str)]


def _reuse_policy_for_step_item(item: dict[str, object], weakened_scopes: set[str]) -> str:
    classification = item.get("preflight_classification")
    if classification == "read_only_analyzable":
        scopes = [scope for scope in item.get("observation_scopes", []) if isinstance(scope, str)]
        if not scopes:
            return "reusable"
        if any(scope in weakened_scopes for scope in scopes):
            return "revalidate"
        return "revalidate"
    return "not_reusable"


def _build_preflight_step_items(check_result: RuntimeResult) -> list[dict[str, object]]:
    weakened_scopes = {
        scope for scope in check_result.outputs.get("weakened_observation_scopes", []) if isinstance(scope, str)
    }
    items: list[dict[str, object]] = []
    for raw_item in check_result.outputs.get("preflight_step_items", []):
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        item["reuse_policy"] = _reuse_policy_for_step_item(item, weakened_scopes)
        items.append(item)
    return items


def plan_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    available_profiles: dict[str, Profile] | None = None,
    guard_probe: GuardProbe | None = None,
    connector_provider: ConnectorProvider | None = None,
) -> RuntimeResult:
    """Build a structured plan without executing effectful business steps."""

    check_result = check_workflow(
        workflow,
        profile=profile,
        available_profiles=available_profiles,
        guard_probe=guard_probe,
        connector_provider=connector_provider,
    )
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
    preflight_step_items = _build_preflight_step_items(check_result)
    weakened_scopes = {scope for scope in base_outputs.get("weakened_observation_scopes", []) if isinstance(scope, str)}
    for item in step_items:
        item["reuse_policy"] = _reuse_policy_for_step_item(item, weakened_scopes)

    blockers = list(base_outputs.get("blockers", []))
    allowed_state = str(base_outputs.get("allowed_state", "blocked"))
    execution_allowed = allowed_state == "allowed"

    plan = ExecutionPlan(
        guard_checks=tuple(item["reference"] for item in guard_items),
        step_names=tuple(item["name"] for item in step_items),
        blockers=tuple(blockers),
    )

    outputs = {
        **base_outputs,
        "plan_ready": check_result.status is not RuntimeStatus.VALIDATION_ERROR,
        "execution_allowed": execution_allowed,
        "guard_items": guard_items,
        "step_items": step_items,
        "run_items": run_items,
        "block_items": block_items,
        "preflight_step_items": preflight_step_items,
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
        preflight_decision=check_result.preflight_decision,
    )


def _build_guard_items(check_result: RuntimeResult, resolution: WorkflowResolution | None) -> list[dict[str, object]]:
    guard_items: list[dict[str, object]] = []
    coverage_items = [item for item in check_result.outputs.get("guard_coverage", []) if isinstance(item, dict)]
    coverage_by_reference = {item.get("reference"): item for item in coverage_items if isinstance(item.get("reference"), str)}

    if resolution is not None and resolution.resolved_guards:
        for index, resolved_guard in enumerate(resolution.resolved_guards):
            operation_result = check_result.operation_results[index] if index < len(check_result.operation_results) else None
            coverage = coverage_by_reference.get(resolved_guard.reference, {})
            if isinstance(resolved_guard, ResolvedGuardExpression):
                detail = check_result.outputs.get("guard_details", [])[index] if index < len(check_result.outputs.get("guard_details", [])) else {}
                guard_items.append(
                    {
                        "reference": resolved_guard.reference,
                        "kind": "expression",
                        "effect": "read_only",
                        "status": coverage.get("status", "unknown"),
                        "relevant": bool(coverage.get("relevant", True)),
                        "evaluated": bool(coverage.get("evaluated", False)),
                        "unknown_reason": coverage.get("unknown_reason"),
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
                        "status": coverage.get("status", "unknown"),
                        "relevant": bool(coverage.get("relevant", True)),
                        "evaluated": bool(coverage.get("evaluated", False)),
                        "unknown_reason": coverage.get("unknown_reason"),
                        "operation_status": None if operation_result is None else operation_result.status,
                    }
                )
        return guard_items

    for reference, coverage in coverage_by_reference.items():
        guard_items.append(
            {
                "reference": reference,
                "kind": "probe_or_expr",
                "effect": "read_only",
                "status": coverage.get("status", "unknown"),
                "relevant": bool(coverage.get("relevant", True)),
                "evaluated": bool(coverage.get("evaluated", False)),
                "unknown_reason": coverage.get("unknown_reason"),
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
    preflight_by_name = {
        item.get("name"): item
        for item in check_result.outputs.get("preflight_step_items", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }

    if resolution is not None and resolution.resolved_steps:
        for step, resolved_step in zip(workflow.steps, resolution.resolved_steps, strict=False):
            preflight_item = preflight_by_name.get(step.name, {})
            if isinstance(resolved_step, ResolvedBuiltinStep):
                classification = classify_preflight_step(step, resolved_step)
                step_items.append(
                    {
                        "name": step.name,
                        "reference": resolved_step.reference,
                        "kind": "builtin",
                        "effect": "effectful",
                        "preflight_classification": classification,
                        "eligibility": "blocked" if blocked else "eligible",
                        "conditional": step.if_ is not None,
                        "condition": step.if_,
                        "condition_status": _condition_status_for_step(step, preflight_item),
                        "observation_scopes": _observation_scopes_for_step(step, resolved_step, preflight_item),
                        "invalidates_scopes": _invalidates_scopes_for_step(resolved_step),
                        "launcher": step.launcher,
                    }
                )
                continue
            if isinstance(resolved_step, ResolvedRunStep):
                classification = classify_preflight_step(step, resolved_step)
                step_items.append(
                    {
                        "name": step.name,
                        "reference": resolved_step.reference,
                        "kind": "run",
                        "effect": "effectful",
                        "preflight_classification": classification,
                        "eligibility": "blocked" if blocked else "eligible",
                        "conditional": step.if_ is not None,
                        "condition": step.if_,
                        "condition_status": _condition_status_for_step(step, preflight_item),
                        "observation_scopes": _observation_scopes_for_step(step, resolved_step, preflight_item),
                        "invalidates_scopes": _invalidates_scopes_for_step(resolved_step),
                        "launcher": None,
                    }
                )
                continue
            classification = classify_preflight_step(step, resolved_step)
            step_items.append(
                {
                    "name": step.name,
                    "reference": resolved_step.reference,
                    "kind": resolved_step.operation.kind,
                    "effect": "read_only" if resolved_step.operation.kind == "probe" else "effectful",
                    "preflight_classification": classification,
                    "eligibility": "blocked" if blocked else "eligible",
                    "conditional": step.if_ is not None,
                    "condition": step.if_,
                    "condition_status": _condition_status_for_step(step, preflight_item),
                    "observation_scopes": _observation_scopes_for_step(step, resolved_step, preflight_item),
                    "invalidates_scopes": _invalidates_scopes_for_step(resolved_step),
                    "launcher": step.launcher,
                }
            )
        return step_items

    for step in workflow.steps:
        classification = classify_preflight_step(step)
        step_items.append(
            {
                "name": step.name,
                "reference": step.operation.uses if step.operation is not None else step.run if step.run is not None else "builtin",
                "kind": "unknown" if step.operation is not None or step.run is not None else "builtin",
                "effect": "unknown" if step.operation is not None or step.run is not None else "effectful",
                "preflight_classification": classification,
                "eligibility": "blocked" if blocked else "unknown",
                "conditional": step.if_ is not None,
                "condition": step.if_,
                "condition_status": None if step.if_ is None else "unknown",
                "observation_scopes": [],
                "invalidates_scopes": [],
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
