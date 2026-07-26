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
from .resolution import ResolvedBuiltinStep, ResolvedConditionExpression, ResolvedGuardBlock, ResolvedRunStep, ResolvedStepBlock, WorkflowResolution, resolve_workflow_references
from .validation import validate_workflow_document
from .value_resolution import ValueResolutionError, resolve_runtime_value


def _condition_status_for_step(step, preflight_item: dict[str, object]) -> str | None:
    if step.if_ is None:
        return None
    status = preflight_item.get("condition_status")
    return cast(str, status) if isinstance(status, str) else "unknown"


def _effective_preflight_classification(
    step,
    resolved_step,
    *,
    block_item: dict[str, object] | None,
) -> str:
    classification = classify_preflight_step(step, resolved_step)
    if isinstance(resolved_step, ResolvedRunStep) and isinstance(block_item, dict):
        status = block_item.get("status")
        if status == "context_applied":
            return "context_only"
    return classification


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


def _fan_out_info_for_step(step, workflow: Workflow, *, condition_status: str | None) -> dict[str, object] | None:
    if step.run is None or step.for_each is None:
        return None
    if condition_status == "false":
        return {
            "enabled": True,
            "source_status": "skipped_whole_step",
            "item_count": None,
            "failure_policy": "strict",
            "register_mode": "aggregate_results" if step.register is not None else "none",
        }
    try:
        value = resolve_runtime_value(step.for_each, workflow, allow_boolean_composition=True)
    except ValueResolutionError:
        return {
            "enabled": True,
            "source_status": "runtime_only",
            "item_count": None,
            "failure_policy": "strict",
            "register_mode": "aggregate_results" if step.register is not None else "none",
        }
    if not isinstance(value, list):
        return {
            "enabled": True,
            "source_status": "runtime_only",
            "item_count": None,
            "failure_policy": "strict",
            "register_mode": "aggregate_results" if step.register is not None else "none",
        }
    return {
        "enabled": True,
        "source_status": "static_known",
        "item_count": len(value),
        "failure_policy": "strict",
        "register_mode": "aggregate_results" if step.register is not None else "none",
    }


def _fan_out_summary(fan_out: dict[str, object] | None) -> str | None:
    if not isinstance(fan_out, dict) or not fan_out.get("enabled"):
        return None
    source_status = fan_out.get("source_status")
    item_count = fan_out.get("item_count")
    if source_status == "static_known" and isinstance(item_count, int):
        return f"fan-out over {item_count} item(s)"
    if source_status == "skipped_whole_step":
        return "fan-out skipped with the whole step"
    return "fan-out cardinality is runtime-only"


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


def _freshness_state_for_scopes(scopes: list[str], weakened_scopes: set[str]) -> str:
    if not scopes:
        return "not_applicable"
    if any(scope in weakened_scopes for scope in scopes):
        return "stale"
    return "fresh"


def _build_preflight_step_items(check_result: RuntimeResult) -> list[dict[str, object]]:
    analysis_tree = getattr(check_result, "analysis_tree", None)
    if analysis_tree is not None and hasattr(analysis_tree, "preflight_step_items"):
        raw_items = getattr(analysis_tree, "preflight_step_items")
    else:
        raw_items = check_result.outputs.get("preflight_step_items", [])
    weakened_scopes = {
        scope for scope in check_result.outputs.get("weakened_observation_scopes", []) if isinstance(scope, str)
    }
    items: list[dict[str, object]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        item["reuse_policy"] = _reuse_policy_for_step_item(item, weakened_scopes)
        register = item.get("register")
        item["produced_registers"] = [] if not isinstance(register, str) else [register]
        outputs = item.get("outputs")
        if isinstance(register, str) and isinstance(outputs, dict):
            item["produced_value_paths"] = [f"step.{register}.outputs.{key}" for key in outputs if isinstance(key, str)]
        else:
            item["produced_value_paths"] = []
        item["freshness_state"] = _freshness_state_for_scopes(
            [scope for scope in item.get("observation_scopes", []) if isinstance(scope, str)],
            weakened_scopes,
        )
        item["invalidated_by_scopes"] = [
            scope
            for scope in item.get("observation_scopes", [])
            if isinstance(scope, str) and scope in weakened_scopes
        ]
        items.append(item)
    return items


def _supporting_step_names_by_scope(preflight_step_items: list[dict[str, object]]) -> dict[str, list[str]]:
    by_scope: dict[str, list[str]] = {}
    for item in preflight_step_items:
        step_name = item.get("name")
        if not isinstance(step_name, str):
            continue
        for scope in item.get("observation_scopes", []):
            if not isinstance(scope, str):
                continue
            by_scope.setdefault(scope, []).append(step_name)
    return by_scope


def _supporting_value_paths_by_scope(preflight_step_items: list[dict[str, object]]) -> dict[str, list[str]]:
    by_scope: dict[str, list[str]] = {}
    for item in preflight_step_items:
        value_paths = [path for path in item.get("produced_value_paths", []) if isinstance(path, str)]
        if not value_paths:
            continue
        for scope in item.get("observation_scopes", []):
            if not isinstance(scope, str):
                continue
            by_scope.setdefault(scope, []).extend(value_paths)
    return by_scope


def _supporting_step_names_for_guard(guard_reference: str, supporting_steps_by_scope: dict[str, list[str]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for scope, step_names in supporting_steps_by_scope.items():
        if scope != guard_reference and scope not in guard_reference:
            continue
        for step_name in step_names:
            if step_name in seen:
                continue
            seen.add(step_name)
            names.append(step_name)
    return names


def _supporting_value_paths_for_guard(guard_reference: str, supporting_value_paths_by_scope: dict[str, list[str]]) -> list[str]:
    value_paths: list[str] = []
    seen: set[str] = set()
    for scope, paths in supporting_value_paths_by_scope.items():
        if scope != guard_reference and scope not in guard_reference:
            continue
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            value_paths.append(path)
    return value_paths


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

    preflight_step_items = _build_preflight_step_items(check_result)
    supporting_steps_by_scope = _supporting_step_names_by_scope(preflight_step_items)
    supporting_value_paths_by_scope = _supporting_value_paths_by_scope(preflight_step_items)
    weakened_scopes = {scope for scope in base_outputs.get("weakened_observation_scopes", []) if isinstance(scope, str)}
    guard_items = _build_guard_items(check_result, resolution, supporting_steps_by_scope, supporting_value_paths_by_scope, weakened_scopes)
    step_items = _build_step_items(check_result, resolution, effective_workflow)
    run_items = _build_run_items(check_result, resolution, effective_workflow)
    block_items = _build_block_items(check_result, resolution, effective_workflow)
    for item in step_items:
        item["reuse_policy"] = _reuse_policy_for_step_item(item, weakened_scopes)
        item["freshness_state"] = _freshness_state_for_scopes(
            [scope for scope in item.get("observation_scopes", []) if isinstance(scope, str)],
            weakened_scopes,
        )
        item["invalidated_by_scopes"] = [
            scope
            for scope in item.get("observation_scopes", [])
            if isinstance(scope, str) and scope in weakened_scopes
        ]
    execution_tree = _build_execution_tree(
        check_result,
        effective_workflow,
        guard_items=guard_items,
        step_items=step_items,
        block_items=block_items,
        preflight_step_items=preflight_step_items,
    )
    ready_to_run_frontier = _build_ready_to_run_frontier(execution_tree)
    execution_tree["ready_to_run_frontier"] = dict(ready_to_run_frontier)

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
        "execution_tree": execution_tree,
        "ready_to_run_frontier": ready_to_run_frontier,
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
        analysis_tree=check_result.analysis_tree,
    )


def _build_guard_items(
    check_result: RuntimeResult,
    resolution: WorkflowResolution | None,
    supporting_steps_by_scope: dict[str, list[str]],
    supporting_value_paths_by_scope: dict[str, list[str]],
    weakened_scopes: set[str],
) -> list[dict[str, object]]:
    guard_items: list[dict[str, object]] = []
    coverage_items = [item for item in check_result.outputs.get("guard_coverage", []) if isinstance(item, dict)]
    coverage_by_reference = {item.get("reference"): item for item in coverage_items if isinstance(item.get("reference"), str)}

    if resolution is not None and resolution.resolved_guards:
        for index, resolved_guard in enumerate(resolution.resolved_guards):
            operation_result = check_result.operation_results[index] if index < len(check_result.operation_results) else None
            coverage = coverage_by_reference.get(resolved_guard.reference, {})
            if isinstance(resolved_guard, ResolvedConditionExpression):
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
                        "supporting_step_names": _supporting_step_names_for_guard(resolved_guard.reference, supporting_steps_by_scope),
                        "supporting_value_paths": _supporting_value_paths_for_guard(resolved_guard.reference, supporting_value_paths_by_scope),
                        "freshness_state": _freshness_state_for_scopes(
                            [scope for scope in detail.get("observation_scopes", []) if isinstance(scope, str)] if isinstance(detail, dict) else [],
                            weakened_scopes,
                        ),
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
                        "supporting_step_names": _supporting_step_names_for_guard(resolved_guard.reference, supporting_steps_by_scope),
                        "supporting_value_paths": _supporting_value_paths_for_guard(resolved_guard.reference, supporting_value_paths_by_scope),
                        "freshness_state": _freshness_state_for_scopes([resolved_guard.reference], weakened_scopes),
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
                "supporting_step_names": _supporting_step_names_for_guard(cast(str, reference), supporting_steps_by_scope),
                "supporting_value_paths": _supporting_value_paths_for_guard(cast(str, reference), supporting_value_paths_by_scope),
                "freshness_state": _freshness_state_for_scopes([cast(str, reference)], weakened_scopes),
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
    block_by_index = {
        item.get("block_index"): item
        for item in check_result.outputs.get("block_items", [])
        if isinstance(item, dict) and isinstance(item.get("block_index"), int)
    }

    if resolution is not None and resolution.resolved_steps:
        for step_index, (step, resolved_step) in enumerate(zip(workflow.steps, resolution.resolved_steps, strict=False)):
            preflight_item = preflight_by_name.get(step.name, {})
            block_item = block_by_index.get(step_index)
            if isinstance(resolved_step, ResolvedBuiltinStep):
                classification = _effective_preflight_classification(step, resolved_step, block_item=block_item)
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
                        "preflight_support": preflight_item.get("preflight_support") if isinstance(preflight_item.get("preflight_support"), dict) else None,
                        "launcher": step.launcher,
                    }
                )
                continue
            if isinstance(resolved_step, ResolvedRunStep):
                classification = _effective_preflight_classification(step, resolved_step, block_item=block_item)
                condition_status = _condition_status_for_step(step, preflight_item)
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
                        "condition_status": condition_status,
                        "observation_scopes": _observation_scopes_for_step(step, resolved_step, preflight_item),
                        "invalidates_scopes": _invalidates_scopes_for_step(resolved_step),
                        "preflight_support": preflight_item.get("preflight_support") if isinstance(preflight_item.get("preflight_support"), dict) else None,
                        "launcher": None,
                        "fan_out": _fan_out_info_for_step(step, workflow, condition_status=condition_status),
                    }
                )
                step_items[-1]["fan_out_summary"] = _fan_out_summary(step_items[-1]["fan_out"])
                continue
            classification = _effective_preflight_classification(step, resolved_step, block_item=block_item)
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
                    "preflight_support": preflight_item.get("preflight_support") if isinstance(preflight_item.get("preflight_support"), dict) else None,
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
                "preflight_support": None,
                "launcher": step.launcher if step.operation is not None else None,
                "fan_out": _fan_out_info_for_step(step, workflow, condition_status=None),
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
                "fan_out": _fan_out_info_for_step(step, workflow, condition_status=None),
                "fan_out_summary": _fan_out_summary(_fan_out_info_for_step(step, workflow, condition_status=None)),
            }
        )
        blocked = True
    return run_items


def _build_execution_tree(
    check_result: RuntimeResult,
    workflow: Workflow,
    *,
    guard_items: list[dict[str, object]],
    step_items: list[dict[str, object]],
    block_items: list[dict[str, object]],
    preflight_step_items: list[dict[str, object]],
) -> dict[str, object]:
    guard_by_reference = {
        item.get("reference"): item
        for item in guard_items
        if isinstance(item, dict) and isinstance(item.get("reference"), str)
    }
    step_by_name = {
        item.get("name"): item for item in step_items if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    preflight_by_name = {
        item.get("name"): item
        for item in preflight_step_items
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    blocks: list[dict[str, object]] = []
    for block_index, declared_block in enumerate(workflow.blocks):
        block_item = next(
            (item for item in block_items if isinstance(item, dict) and item.get("block_index") == block_index),
            {},
        )
        block_node = {
            "id": f"block:{block_index}",
            "block_index": block_index,
            "type": block_item.get("type", "guards" if isinstance(declared_block, GuardBlock) else "steps"),
            "status": block_item.get("status", "pending"),
            "runtime_status": "not_started",
            "freshness_state": "not_applicable",
            "active_profile": block_item.get("active_profile"),
            "children": [],
        }
        if isinstance(declared_block, GuardBlock):
            block_node["children"] = [
                {
                    "id": f"block:{block_index}:guard:{guard_index}",
                    "runtime_status": "not_started",
                    "revalidated": False,
                    "planned_observation": None,
                    "runtime_observation": None,
                    "divergence_status": "not_applicable",
                    "divergence_reason": None,
                    **dict(guard_by_reference.get(guard.reference, {"reference": guard.reference})),
                }
                for guard_index, guard in enumerate(declared_block.guards)
            ]
        else:
            block_node["children"] = [
                {
                    "id": f"block:{block_index}:step:{step_index}",
                    "runtime_status": "not_started",
                    "revalidated": False,
                    "planned_observation": None
                    if step.name not in preflight_by_name
                    else dict(preflight_by_name[step.name].get("outputs", {})),
                    "runtime_observation": None,
                    "divergence_status": "not_checked" if step.name in preflight_by_name else "not_applicable",
                    "divergence_reason": None,
                    **dict(step_by_name.get(step.name, {"name": step.name})),
                    "preflight": dict(preflight_by_name[step.name]) if step.name in preflight_by_name else None,
                    "fan_out": dict(step_by_name[step.name].get("fan_out", {})) if step.name in step_by_name and isinstance(step_by_name[step.name].get("fan_out"), dict) else None,
                }
                for step_index, step in enumerate(declared_block.steps)
            ]
        child_freshness = {
            child.get("freshness_state")
            for child in block_node["children"]
            if isinstance(child, dict) and isinstance(child.get("freshness_state"), str)
        }
        if "stale" in child_freshness:
            block_node["freshness_state"] = "stale"
        elif "fresh" in child_freshness:
            block_node["freshness_state"] = "fresh"
        blocks.append(block_node)

    return {
        "workflow": workflow.workflow,
        "allowed_state": check_result.outputs.get("allowed_state"),
        "analysis_complete": check_result.outputs.get("analysis_complete"),
        "blocks": blocks,
    }


def _build_ready_to_run_frontier(execution_tree: dict[str, object]) -> dict[str, object]:
    prepared_node_ids: list[str] = []
    requires_runtime_node_ids: list[str] = []
    blocked_node_ids: list[str] = []
    for block in execution_tree.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for child in block.get("children", []):
            if not isinstance(child, dict):
                continue
            node_id = child.get("id")
            if not isinstance(node_id, str):
                continue
            status = child.get("status")
            eligibility = child.get("eligibility")
            preflight = child.get("preflight")
            if status in {"passed", "blocked"}:
                prepared_node_ids.append(node_id)
                if status == "blocked":
                    blocked_node_ids.append(node_id)
                continue
            if isinstance(preflight, dict) and preflight.get("status") in {"interpreted", "skipped"} and child.get("reuse_policy") == "reusable":
                prepared_node_ids.append(node_id)
                continue
            if eligibility == "blocked":
                blocked_node_ids.append(node_id)
                continue
            requires_runtime_node_ids.append(node_id)
    return {
        "allowed_state": execution_tree.get("allowed_state"),
        "prepared_node_ids": prepared_node_ids,
        "requires_runtime_node_ids": requires_runtime_node_ids,
        "blocked_node_ids": blocked_node_ids,
    }
