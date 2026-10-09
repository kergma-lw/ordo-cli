"""Explain mode for structured runtime reasoning."""

from __future__ import annotations

import json
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, RunBlock, Step, StepBlock, Workflow

from .executing import execute_workflow
from .planning import plan_workflow
from .providers import ConnectorProvider, GuardProbe, StepExecutor


def explain_workflow_outline(workflow: Workflow) -> RuntimeResult:
    """Return a static outline of an already assembled workflow.

    This intentionally does not validate, resolve, activate, or observe the
    workflow.  It is an orientation surface, not a readiness decision.
    """

    diagnostics: list[Diagnostic] = []
    pre_run: list[dict[str, object]] = []
    body: list[dict[str, object]] = []
    for block_index, block in enumerate(workflow.blocks):
        target = pre_run if _is_pre_run_block(block) else body
        outlined_block = _outline_block(block, block_index, diagnostics)
        if target and target[-1].get("kind") == "guards" and outlined_block.get("kind") == "guards":
            previous_items = target[-1].get("items")
            current_items = outlined_block.get("items")
            if isinstance(previous_items, list) and isinstance(current_items, list):
                previous_items.extend(current_items)
                continue
        target.append(outlined_block)

    outline: dict[str, object] = {"workflow": workflow.workflow, "phases": []}
    if pre_run:
        outline["phases"].append({"kind": "pre_run", "items": pre_run})
    outline["phases"].append({"kind": "body", "items": body})
    return RuntimeResult(
        mode=Mode.EXPLAIN,
        status=RuntimeStatus.RESOLUTION_ERROR if diagnostics else RuntimeStatus.OK,
        diagnostics=tuple(diagnostics),
        outputs={"outline": outline},
    )


def _is_pre_run_block(block: GuardBlock | StepBlock | RunBlock) -> bool:
    return isinstance(block, StepBlock) and bool(block.steps) and all(step.run_origin == "playbook_pre_run" for step in block.steps)


def _outline_block(
    block: GuardBlock | StepBlock | RunBlock,
    block_index: int,
    diagnostics: list[Diagnostic],
) -> dict[str, object]:
    if isinstance(block, GuardBlock):
        return {"kind": "guards", "items": [_outline_guard(guard) for guard in block.guards]}
    if isinstance(block, RunBlock):
        item = {"kind": "run", "label": "workflow invocation"}
        if block.if_ is not None:
            item["controls"] = [{"kind": "if", "expression": _symbolic_expression(block.if_)}]
        _append_unavailable_run_diagnostic(item, block.run, block.resolved_path, ("blocks", str(block_index)), diagnostics)
        return item
    return {"kind": "steps", "items": [_outline_step(step, block_index, step_index, diagnostics) for step_index, step in enumerate(block.steps)]}


def _outline_step(step: Step, block_index: int, step_index: int, diagnostics: list[Diagnostic]) -> dict[str, object]:
    item: dict[str, object] = {"kind": "run" if step.run is not None else "step", "label": step.name}
    if step.register is not None:
        item["register"] = step.register
    controls: list[dict[str, str]] = []
    if step.if_ is not None:
        controls.append({"kind": "if", "expression": _symbolic_expression(step.if_)})
    if step.gate is not None:
        controls.append({"kind": "gate", "expression": _symbolic_expression(step.gate)})
    if step.for_each is not None:
        controls.append({"kind": "loop", "expression": _symbolic_expression(step.for_each)})
    if controls:
        item["controls"] = controls
    if step.run is not None:
        _append_unavailable_run_diagnostic(item, step.run, step.resolved_run_path, ("blocks", str(block_index), "steps", str(step_index)), diagnostics)
    return item


def _outline_guard(guard: Guard) -> dict[str, str]:
    expression = guard.operation.uses if guard.operation is not None else guard.expr or "<guard>"
    return {"kind": "guard", "expression": _symbolic_expression(expression)}


def _symbolic_expression(value: object) -> str:
    """Keep authored control text symbolic without exposing a state path."""

    if isinstance(value, str):
        rendered = value
    else:
        rendered = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if "state." in rendered or "state[" in rendered:
        return "<state expression>"
    return rendered


def _append_unavailable_run_diagnostic(
    item: dict[str, object],
    run: str,
    resolved_path: str | None,
    path: tuple[str, ...],
    diagnostics: list[Diagnostic],
) -> None:
    if resolved_path is None or Path(resolved_path).exists():
        return
    item["structural_status"] = "unavailable"
    diagnostics.append(
        Diagnostic(
            code="explain.run.unavailable",
            level="error",
            message="A referenced workflow invocation is unavailable",
            path=path,
            details={},
        )
    )


def assess_workflow_readiness(
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
        profile_name = result.outputs.get("workflow_profile_declared")
        if isinstance(profile_name, str) and any(diagnostic.code == "runtime.workflow.profile.not_available" for diagnostic in result.diagnostics):
            return {
                "category": "workflow_profile",
                "allowed": False,
                "why": f"The workflow declares execution profile '{profile_name}', but that profile is not available in the current execution context",
                "blockers": [profile_name],
            }
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
    nested_gate_blockers = [item for item in result.outputs.get("nested_gate_blockers", []) if isinstance(item, dict)]
    if gate_blockers:
        step_items = [item for item in result.outputs.get("preflight_step_items", []) if isinstance(item, dict)]
        why = "A reachable step is blocked by admission checks established from current read-only knowledge"
        if nested_gate_blockers:
            first = nested_gate_blockers[0]
            item_value = first.get("expanded_item")
            gate_reports = first.get("gate_reports") if isinstance(first.get("gate_reports"), list) else []
            failed_expressions = []
            if gate_reports and isinstance(gate_reports[0], dict):
                failed = gate_reports[0].get("failed_causes")
                if not isinstance(failed, list):
                    failed = gate_reports[0].get("failed")
                if isinstance(failed, list):
                    failed_expressions = [
                        item.get("rendered") or item.get("expression")
                        for item in failed
                        if isinstance(item, dict) and isinstance(item.get("rendered") or item.get("expression"), str)
                    ]
            why = "A nested gate inside fan-out preflight checks failed for at least one expanded item"
            if isinstance(item_value, str):
                why = f"Nested gate failed for fan-out item '{item_value}'"
            if failed_expressions:
                why = f"{why}: {failed_expressions[0]}"
        return {
            "category": "gate",
            "allowed": False,
            "why": why,
            "blockers": gate_blockers,
            "step_gate_details": [item.get("gate_report") for item in step_items if item.get("name") in gate_blockers and isinstance(item.get("gate_report"), dict)],
            "nested_gate_blockers": nested_gate_blockers,
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
        if reason == "preflight_step_not_analyzable":
            details = first.get("details") if isinstance(first.get("details"), dict) else {}
            classification = details.get("classification") if isinstance(details.get("classification"), str) else None
            reference = details.get("reference") if isinstance(details.get("reference"), str) else None
            why = "A preflight step could not be fully analyzed from current read-only knowledge"
            if classification == "read_only_unanalyzable":
                why = "A read-only preflight step could not be fully analyzed from current knowledge, so nested gate results remain unavailable"
            return {
                "category": "preflight_step",
                "allowed": False,
                "why": why,
                "blockers": [] if step_name is None else [step_name],
                "preflight_halts": preflight_halts,
                "preflight_support_steps": _preflight_support_steps(result),
                "reference": reference,
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
            f"Based on current observed inputs and state, all read-only observations completed and the next runnable step is '{result.outputs.get('frontier_ready_step')}'"
            if isinstance(result.outputs.get("frontier_ready_step"), str)
            else "Based on current observed inputs and state, no known blocker prevents execution now"
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
        if any(diagnostic.code == "runtime.workflow.profile.not_available" for diagnostic in result.diagnostics):
            return [
                {
                    "action": "make_workflow_profile_available",
                    "reason": "Provide the workflow-declared profile in the current playbook or execution context before retrying",
                }
            ]
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
        nested_gate_blockers = [item for item in result.outputs.get("nested_gate_blockers", []) if isinstance(item, dict)]
        if nested_gate_blockers:
            first = nested_gate_blockers[0]
            item_value = first.get("expanded_item")
            item_text = item_value if isinstance(item_value, str) else first.get("expanded_item_index")
            return [
                {
                    "action": "satisfy_nested_step_gate",
                    "reason": f"Resolve the failing nested gate for fan-out item '{item_text}' before retrying",
                }
            ]
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
        if reason == "preflight_step_not_analyzable":
            return [
                {
                    "action": "analyze_unanalyzable_preflight_step",
                    "reason": f"Inspect the preflight step '{step_name}' because nested fan-out or fragment logic could not yet be explained from current read-only knowledge",
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
