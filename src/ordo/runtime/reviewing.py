"""Review mode for authoring-oriented findings over the shared analysis tree."""

from __future__ import annotations

from ordo.model.profile import Profile
from ordo.model.runtime import Mode, RuntimeResult, RuntimeStatus
from ordo.model.workflow import GuardBlock, Workflow

from .checking import check_workflow
from .providers import ConnectorProvider, GuardProbe


def review_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    available_profiles: dict[str, Profile] | None = None,
    guard_probe: GuardProbe | None = None,
    connector_provider: ConnectorProvider | None = None,
) -> RuntimeResult:
    """Return authoring findings without changing runtime executability semantics."""

    check_result = check_workflow(
        workflow,
        profile=profile,
        available_profiles=available_profiles,
        guard_probe=guard_probe,
        connector_provider=connector_provider,
    )
    if check_result.status in {RuntimeStatus.VALIDATION_ERROR, RuntimeStatus.RESOLUTION_ERROR}:
        return RuntimeResult(
            mode=Mode.REVIEW,
            status=check_result.status,
            diagnostics=check_result.diagnostics,
            plan=check_result.plan,
            outputs={
                **dict(check_result.outputs),
                "review_status": "unavailable",
                "finding_count": 0,
                "findings": [],
            },
            operation_results=check_result.operation_results,
            failed_guard=check_result.failed_guard,
            failed_step=check_result.failed_step,
            preflight_decision=check_result.preflight_decision,
            analysis_tree=check_result.analysis_tree,
        )

    findings = _build_review_findings(workflow, check_result, profile=profile)
    outputs = {
        "review_status": "clean" if not findings else "needs_attention",
        "finding_count": len(findings),
        "findings": findings,
        "categories": sorted({item["category"] for item in findings if isinstance(item.get("category"), str)}),
        "check_snapshot": {
            "status": check_result.status.value,
            "allowed_state": check_result.outputs.get("allowed_state"),
            "analysis_complete": check_result.outputs.get("analysis_complete"),
            "incomplete_reasons": [
                reason for reason in check_result.outputs.get("incomplete_reasons", []) if isinstance(reason, str)
            ],
        },
        "active_profile": check_result.outputs.get("active_profile"),
    }
    return RuntimeResult(
        mode=Mode.REVIEW,
        status=RuntimeStatus.OK,
        diagnostics=check_result.diagnostics,
        plan=check_result.plan,
        outputs=outputs,
        operation_results=check_result.operation_results,
        failed_guard=check_result.failed_guard,
        failed_step=check_result.failed_step,
        preflight_decision=check_result.preflight_decision,
        analysis_tree=check_result.analysis_tree,
    )


def _build_review_findings(workflow: Workflow, check_result: RuntimeResult, *, profile: Profile | None) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    findings.extend(_find_missing_input_validation(workflow, check_result, profile=profile))
    findings.extend(_find_missing_recommended_observations(check_result))
    return findings


def _find_missing_input_validation(
    workflow: Workflow,
    check_result: RuntimeResult,
    *,
    profile: Profile | None,
) -> list[dict[str, object]]:
    input_usages = _input_usages_from_result(check_result)
    if not input_usages:
        return []

    analysis_workflow = getattr(check_result, "analysis_tree", None)
    guard_workflow = workflow
    if analysis_workflow is not None and hasattr(analysis_workflow, "workflow") and isinstance(analysis_workflow.workflow, Workflow):
        guard_workflow = analysis_workflow.workflow

    early_guard_expressions: list[str] = []
    for block in guard_workflow.blocks:
        if isinstance(block, GuardBlock):
            early_guard_expressions.extend(guard.reference for guard in block.guards if isinstance(guard.reference, str))

    findings: list[dict[str, object]] = []
    for usage in input_usages:
        input_name = usage.get("input")
        if not isinstance(input_name, str):
            continue
        classification = _review_input_classification(usage, profile=profile)
        if classification == "ambient_profile_context":
            continue
        if classification not in {"control_input", "effect_target_input"}:
            continue
        needle = f"inputs.{input_name}"
        if any(needle in expression for expression in early_guard_expressions):
            continue
        findings.append(
            {
                "code": "review.workflow.input_validation_missing",
                "level": "warning",
                "category": "input_validation",
                "message": f"Input '{input_name}' is not validated in early guards",
                "path": ["inputs", input_name],
                "evidence": {
                    "input": input_name,
                    "classification": classification,
                    "usage_sites": [dict(site) for site in usage.get("evidence", []) if isinstance(site, dict)],
                    "reason": "no early guard references this input before step execution begins",
                },
            }
        )
    return findings


def _input_usages_from_result(check_result: RuntimeResult) -> list[dict[str, object]]:
    analysis_tree = getattr(check_result, "analysis_tree", None)
    if analysis_tree is None or not hasattr(analysis_tree, "input_usages"):
        return []
    return [dict(item) for item in getattr(analysis_tree, "input_usages") if isinstance(item, dict)]


def _review_input_classification(usage: dict[str, object], *, profile: Profile | None) -> str:
    base = usage.get("classification")
    input_name = usage.get("input")
    if not isinstance(base, str) or not isinstance(input_name, str):
        return "unknown"
    if profile is not None and input_name in profile.inputs and base != "control_input":
        return "ambient_profile_context"
    return base


def _find_missing_recommended_observations(check_result: RuntimeResult) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for item in check_result.outputs.get("preflight_step_items", []):
        if not isinstance(item, dict):
            continue
        support = item.get("preflight_support")
        if not isinstance(support, dict):
            continue
        strength = support.get("strength")
        missing = support.get("missing_observations")
        if strength not in {"weak", "partial"} or not isinstance(missing, list) or not missing:
            continue
        findings.append(
            {
                "code": "review.workflow.missing_recommended_observations",
                "level": "warning",
                "category": "preflight_support",
                "message": f"Step '{item.get('name')}' is missing recommended preflight observations",
                "path": ["blocks", str(item.get("block_index")), "steps", str(item.get("step_index"))],
                "evidence": {
                    "step": item.get("name"),
                    "reference": item.get("reference"),
                    "strength": strength,
                    "missing_observations": list(missing),
                },
            }
        )
    return findings
