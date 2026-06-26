"""Check mode for pre-execution validation, resolution, and guard analysis."""

from __future__ import annotations

from collections.abc import Callable

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Workflow

from .profiles import apply_profile_to_workflow
from .resolution import ResolvedOperation, resolve_workflow_references
from .validation import validate_workflow_document

GuardProbe = Callable[[ResolvedOperation, Workflow], OperationResult]


def check_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    guard_probe: GuardProbe | None = None,
) -> RuntimeResult:
    """Run check mode without executing effectful business steps."""

    validation_report = validate_workflow_document(workflow.to_contract())
    if not validation_report.ok:
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.VALIDATION_ERROR,
            diagnostics=validation_report.diagnostics,
            plan=ExecutionPlan(),
            outputs={"can_execute": False, "blockers": [], "checked_guards": []},
        )

    active_profile = None
    active_overrides = ()
    effective_workflow = workflow

    if profile is not None:
        applied = apply_profile_to_workflow(workflow, profile)
        active_profile = applied.active_profile
        active_overrides = applied.active_overrides
        if not applied.ok or applied.workflow is None:
            return RuntimeResult(
                mode=Mode.CHECK,
                status=RuntimeStatus.VALIDATION_ERROR,
                diagnostics=applied.diagnostics,
                plan=ExecutionPlan(),
                outputs={
                    "can_execute": False,
                    "blockers": [],
                    "checked_guards": [],
                    "active_profile": active_profile,
                    "active_overrides": [override.to_contract() for override in active_overrides],
                },
            )
        effective_workflow = applied.workflow

    resolution = resolve_workflow_references(
        effective_workflow,
        active_overrides=active_overrides,
    )
    if not resolution.ok:
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.RESOLUTION_ERROR,
            diagnostics=resolution.diagnostics,
            plan=ExecutionPlan(
                guard_checks=tuple(guard.reference for guard in effective_workflow.guards),
                step_names=tuple(step.name for step in effective_workflow.steps),
                blockers=(),
            ),
            outputs={
                    "can_execute": False,
                    "blockers": [],
                    "checked_guards": [guard.reference for guard in effective_workflow.guards],
                    "active_profile": active_profile,
                    "active_overrides": [override.to_contract() for override in active_overrides],
                },
        )

    probe = guard_probe or _default_guard_probe
    diagnostics: list[Diagnostic] = []
    operation_results: list[OperationResult] = []
    blockers: list[str] = []
    failed_guard: str | None = None

    for resolved_guard in resolution.resolved_guards:
        result = probe(resolved_guard, effective_workflow)
        operation_results.append(result)
        diagnostics.extend(result.diagnostics)
        if result.status != "ok":
            blockers.append(resolved_guard.reference)
            if failed_guard is None:
                failed_guard = resolved_guard.reference

    if blockers:
        return RuntimeResult(
            mode=Mode.CHECK,
            status=RuntimeStatus.GUARD_FAILED,
            diagnostics=tuple(diagnostics),
            plan=ExecutionPlan(
                guard_checks=tuple(result.reference for result in resolution.resolved_guards),
                step_names=tuple(step.name for step in effective_workflow.steps),
                blockers=tuple(blockers),
            ),
            outputs={
                "can_execute": False,
                "blockers": blockers,
                "checked_guards": [result.reference for result in resolution.resolved_guards],
                "active_profile": active_profile,
                "active_overrides": [override.to_contract() for override in active_overrides],
            },
            operation_results=tuple(operation_results),
            failed_guard=failed_guard,
        )

    return RuntimeResult(
        mode=Mode.CHECK,
        status=RuntimeStatus.OK,
        diagnostics=tuple(diagnostics),
        plan=ExecutionPlan(
            guard_checks=tuple(result.reference for result in resolution.resolved_guards),
            step_names=tuple(step.name for step in effective_workflow.steps),
            blockers=(),
        ),
        outputs={
            "can_execute": True,
            "blockers": [],
            "checked_guards": [result.reference for result in resolution.resolved_guards],
            "active_profile": active_profile,
            "active_overrides": [override.to_contract() for override in active_overrides],
        },
        operation_results=tuple(operation_results),
    )


def _default_guard_probe(resolved_guard: ResolvedOperation, workflow: Workflow) -> OperationResult:
    """Default side-effect-free probe backed by canonical connector operations."""

    from ordo.connectors.operations import evaluate_probe

    return evaluate_probe(resolved_guard, workflow)
