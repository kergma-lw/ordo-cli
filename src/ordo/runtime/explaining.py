"""Explain mode for structured runtime reasoning."""

from __future__ import annotations

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
    guard_probe: GuardProbe | None = None,
    connector_provider: ConnectorProvider | None = None,
) -> RuntimeResult:
    """Explain why execution is blocked or allowed without executing business steps."""

    plan_result = plan_workflow(workflow, profile=profile, guard_probe=guard_probe, connector_provider=connector_provider)
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
        return {
            "category": "execution",
            "allowed": False,
            "why": "Execution started but a step failed",
            "blockers": [result.failed_step] if result.failed_step is not None else [],
            "step_condition_details": step_condition_details,
        }

    return {
        "category": "ok",
        "allowed": bool(result.outputs.get("can_execute", True)),
        "why": "No known blocker prevents execution now",
        "blockers": [],
    }


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
        return [
            {
                "action": "repair_failed_step",
                "reason": "Inspect the failed step result and correct the execution issue",
            }
        ]

    return [
        {
            "action": "execute_workflow",
            "reason": "Validation, resolution, and guards currently allow execution",
        }
    ]
