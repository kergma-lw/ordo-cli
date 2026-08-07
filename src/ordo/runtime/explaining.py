"""Explain mode for structured runtime reasoning."""

from __future__ import annotations

from pathlib import Path

from ordo.model.profile import Profile
from ordo.model.runtime import Mode, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Workflow

from .executing import execute_workflow
from .planning import plan_workflow
from .providers import ConnectorProvider, GuardProbe, StepExecutor


def explain_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    available_profiles: dict[str, Profile] | None = None,
    profile_working_directories: dict[str, Path | None] | None = None,
    guard_probe: GuardProbe | None = None,
    connector_provider: ConnectorProvider | None = None,
) -> RuntimeResult:
    """Explain why execution is blocked or allowed without executing business steps."""

    plan_result = plan_workflow(
        workflow,
        profile=profile,
        available_profiles=available_profiles,
        profile_working_directories=profile_working_directories,
        guard_probe=guard_probe,
        connector_provider=connector_provider,
    )
    return explain_runtime_result(plan_result)


def explain_runtime_result(result: RuntimeResult) -> RuntimeResult:
    """Convert a runtime result into a stable structured explanation surface."""

    outputs = dict(result.outputs)
    explanation = _build_explanation(result)
    next_actions = _infer_next_actions(result)

    outputs.update(
        {
            "explanation": explanation,
            "next_actions": next_actions,
            "reason_category": explanation["category"],
        }
    )

    return RuntimeResult(
        mode=Mode.EXPLAIN,
        status=result.status,
        diagnostics=result.diagnostics,
        plan=result.plan,
        outputs=outputs,
        operation_results=result.operation_results,
        failed_guard=result.failed_guard,
        failed_step=result.failed_step,
        preflight_decision=result.preflight_decision,
        analysis_tree=result.analysis_tree,
    )


def explain_execution_result(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    guard_probe: GuardProbe | None = None,
    step_executor: StepExecutor | None = None,
    connector_provider: ConnectorProvider | None = None,
) -> RuntimeResult:
    """Execute and then explain the resulting runtime decision surface."""

    execution_result = execute_workflow(
        workflow,
        profile=profile,
        guard_probe=guard_probe,
        step_executor=step_executor,
        connector_provider=connector_provider,
    )
    return explain_runtime_result(execution_result)


def _build_explanation(result: RuntimeResult) -> dict[str, object]:
    allowed_state = result.outputs.get("allowed_state")
    analysis_complete = bool(result.outputs.get("analysis_complete", True))
    incomplete_reasons = [reason for reason in result.outputs.get("incomplete_reasons", []) if isinstance(reason, str)]

    if result.status is RuntimeStatus.VALIDATION_ERROR:
        return {
            "category": "validation",
            "allowed": False,
            "why": "Workflow is invalid and cannot proceed to resolution or execution",
            "blockers": [diagnostic.code for diagnostic in result.diagnostics],
        }

    if result.status is RuntimeStatus.RESOLUTION_ERROR:
        return {
            "category": "resolution",
            "allowed": False,
            "why": "Workflow references could not be resolved against the public connector surface",
            "blockers": [diagnostic.details.get("reference", diagnostic.code) for diagnostic in result.diagnostics],
        }

    if result.status is RuntimeStatus.GUARD_FAILED:
        guard_details = [detail for detail in result.outputs.get("guard_details", []) if isinstance(detail, dict)]
        bootstrap_details = [detail for detail in result.outputs.get("bootstrap_details", []) if isinstance(detail, dict)]
        executed_steps = [name for name in result.outputs.get("executed_steps", []) if isinstance(name, str)]
        if any(detail.get("status") != "ok" for detail in bootstrap_details):
            return {
                "category": "bootstrap",
                "allowed": False,
                "why": "A connector family bootstrap prerequisite failed before operation-local logic could proceed",
                "blockers": [detail.get("namespace") for detail in bootstrap_details if detail.get("status") != "ok"],
                "bootstrap_details": bootstrap_details,
            }
        return {
            "category": "guard",
            "allowed": False,
            "why": (
                "One or more guards blocked execution before a later step block could run"
                if executed_steps
                else "One or more guards blocked execution before any business step could run"
            ),
            "blockers": list(result.outputs.get("blockers", [])),
            "guard_details": guard_details,
            "executed_steps": executed_steps,
        }

    if result.status is RuntimeStatus.EXECUTION_ERROR:
        step_condition_details = [detail for detail in result.outputs.get("step_condition_details", []) if isinstance(detail, dict)]
        step_gate_details = [detail for detail in result.outputs.get("step_gate_details", []) if isinstance(detail, dict)]
        fan_out_failure = result.outputs.get("fan_out_failure") if isinstance(result.outputs.get("fan_out_failure"), dict) else None
        gate_blockers = [name for name in result.outputs.get("gate_blockers", []) if isinstance(name, str)]
        return {
            "category": "gate" if gate_blockers else "execution",
            "allowed": False,
            "why": (
                "Execution reached a gated step but admission checks did not pass"
                if gate_blockers
                else "Execution started but a fan-out item failed" if fan_out_failure is not None else "Execution started but a step failed"
            ),
            "blockers": gate_blockers or ([result.failed_step] if result.failed_step is not None else []),
            "step_condition_details": step_condition_details,
            "step_gate_details": step_gate_details,
            "fan_out_failure": fan_out_failure,
        }

    gate_blockers = [name for name in result.outputs.get("gate_blockers", []) if isinstance(name, str)]
    if gate_blockers:
        step_items = [item for item in result.outputs.get("preflight_step_items", []) if isinstance(item, dict)]
        return {
            "category": "gate",
            "allowed": False,
            "why": "A reachable step is blocked by admission checks established from current read-only knowledge",
            "blockers": gate_blockers,
            "step_gate_details": [item.get("gate_report") for item in step_items if item.get("name") in gate_blockers and isinstance(item.get("gate_report"), dict)],
        }

    preflight_halts = [item for item in result.outputs.get("preflight_halts", []) if isinstance(item, dict)]
    if preflight_halts:
        first = preflight_halts[0]
        step_name = first.get("step_name") if isinstance(first.get("step_name"), str) else None
        reason = first.get("reason") if isinstance(first.get("reason"), str) else None
        if reason == "read_only_step_failed":
            return {
                "category": "preflight_step",
                "allowed": False,
                "why": "A read-only observation step failed before workflow readiness could be established",
                "blockers": [] if step_name is None else [step_name],
                "preflight_halts": preflight_halts,
                "preflight_support_steps": _preflight_support_steps(result),
            }
        if reason == "gate_unknown":
            step_items = [item for item in result.outputs.get("preflight_step_items", []) if isinstance(item, dict)]
            return {
                "category": "gate",
                "allowed": False,
                "why": "A step gate could not yet be fully established from current read-only knowledge",
                "blockers": [] if step_name is None else [step_name],
                "step_gate_details": [item.get("gate_report") for item in step_items if item.get("name") == step_name and isinstance(item.get("gate_report"), dict)],
                "preflight_halts": preflight_halts,
            }

    if allowed_state == "unknown" or not analysis_complete:
        fan_out_items = [item for item in result.outputs.get("run_items", []) if isinstance(item, dict) and isinstance(item.get("fan_out"), dict)]
        return {
            "category": "incomplete",
            "allowed": False,
            "why": "Runtime has not yet established whether execution is allowed from current pre-execution knowledge",
            "blockers": [],
            "incomplete_reasons": incomplete_reasons,
            "preflight_halts": preflight_halts,
            "preflight_support_steps": _preflight_support_steps(result),
            "fan_out_items": fan_out_items,
        }

    return {
        "category": "ok",
        "allowed": allowed_state == "allowed" if isinstance(allowed_state, str) else bool(result.outputs.get("can_execute", True)),
        "why": (
            f"All read-only observations completed and the next runnable step is '{result.outputs.get('frontier_ready_step')}'"
            if isinstance(result.outputs.get("frontier_ready_step"), str)
            else "No known blocker prevents execution now"
        ),
        "blockers": [],
        "preflight_support_steps": _preflight_support_steps(result),
        "fan_out_items": [item for item in result.outputs.get("run_items", []) if isinstance(item, dict) and isinstance(item.get("fan_out"), dict)],
    }


def _preflight_support_steps(result: RuntimeResult) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for item in result.outputs.get("step_items", []):
        if not isinstance(item, dict):
            continue
        support = item.get("preflight_support")
        if not isinstance(support, dict):
            continue
        strength = support.get("strength")
        if not isinstance(strength, str) or strength == "not_applicable":
            continue
        items.append(
            {
                "name": item.get("name"),
                "reference": item.get("reference"),
                "preflight_support": dict(support),
            }
        )
    return items


def _infer_next_actions(result: RuntimeResult) -> list[dict[str, str]]:
    if result.status is RuntimeStatus.VALIDATION_ERROR:
        return [
            {
                "action": "fix_validation_errors",
                "reason": "Resolve the reported validation diagnostics before retrying",
            }
        ]

    if result.status is RuntimeStatus.RESOLUTION_ERROR:
        return [
            {
                "action": "fix_operation_references",
                "reason": "Use known public operations or an explicit local namespace",
            }
        ]

    if result.status is RuntimeStatus.GUARD_FAILED:
        bootstrap_details = [detail for detail in result.outputs.get("bootstrap_details", []) if isinstance(detail, dict)]
        if any(detail.get("status") != "ok" for detail in bootstrap_details):
            return [
                {
                    "action": "repair_connector_bootstrap",
                    "reason": "Resolve the shared connector prerequisite failure before retrying",
                }
            ]
        return [
            {
                "action": "resolve_blocking_guards",
                "reason": "Address the blocking guard conditions before execution",
            }
        ]

    if result.status is RuntimeStatus.EXECUTION_ERROR:
        if any(isinstance(name, str) for name in result.outputs.get("gate_blockers", [])):
            return [
                {
                    "action": "satisfy_step_gate",
                    "reason": "Resolve the failed or unknown gate conditions before retrying the blocked step",
                }
            ]
        return [
            {
                "action": "repair_failed_step",
                "reason": "Inspect the failed step result and correct the execution issue",
            }
        ]

    if any(isinstance(name, str) for name in result.outputs.get("gate_blockers", [])):
        return [
            {
                "action": "satisfy_step_gate",
                "reason": "Resolve the failed admission checks before treating the gated step as runnable",
            }
        ]

    preflight_halts = [item for item in result.outputs.get("preflight_halts", []) if isinstance(item, dict)]
    if preflight_halts:
        first = preflight_halts[0]
        reason = first.get("reason")
        step_name = first.get("step_name")
        if reason == "read_only_step_failed":
            return [
                {
                    "action": "repair_read_only_observation",
                    "reason": f"Fix the failing read-only step '{step_name}' before retrying preflight",
                }
            ]

    if result.outputs.get("allowed_state") == "unknown" or not bool(result.outputs.get("analysis_complete", True)):
        return [
            {
                "action": "complete_preflight_analysis",
                "reason": "Resolve incomplete preflight knowledge before treating execution as allowed",
            }
        ]

    return [
        {
            "action": "execute_workflow",
            "reason": "Validation, resolution, and guards currently allow execution",
        }
    ]
