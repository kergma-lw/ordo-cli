"""Profile composition and explicit override handling."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Override, Profile
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Workflow


@dataclass(frozen=True, slots=True)
class ProfileCompositionResult:
    """Structured result for profile composition."""

    status: RuntimeStatus
    diagnostics: tuple[Diagnostic, ...] = ()
    profile: Profile | None = None
    active_profiles: tuple[str, ...] = ()
    active_overrides: tuple[Override, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is RuntimeStatus.OK


@dataclass(frozen=True, slots=True)
class WorkflowProfileApplicationResult:
    """Structured result for applying a profile to workflow defaults."""

    status: RuntimeStatus
    diagnostics: tuple[Diagnostic, ...] = ()
    workflow: Workflow | None = None
    active_profile: str | None = None
    active_overrides: tuple[Override, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is RuntimeStatus.OK


def compose_profiles(*profiles: Profile, name: str | None = None) -> ProfileCompositionResult:
    """Compose profiles left-to-right without silent semantic mutation."""

    diagnostics: list[Diagnostic] = []
    merged_inputs: dict[str, object] = {}
    merged_checks: list[str] = []
    merged_overrides: list[Override] = []
    input_sources: dict[str, str] = {}
    override_sources: dict[str, str] = {}

    for profile in profiles:
        for key, value in profile.inputs.items():
            if key in merged_inputs and merged_inputs[key] != value:
                diagnostics.append(
                    _diagnostic(
                        code="composition.profile.input_conflict",
                        message=f"Profile input '{key}' conflicts with an earlier profile value",
                        path=("inputs", key),
                        profile=profile.name,
                        first_profile=input_sources[key],
                        previous_value=merged_inputs[key],
                        new_value=value,
                    )
                )
                continue
            if key not in merged_inputs:
                merged_inputs[key] = value
                input_sources[key] = profile.name

        for check in profile.checks:
            if check not in merged_checks:
                merged_checks.append(check)

        for override in profile.overrides:
            if override.target in override_sources:
                diagnostics.append(
                    _diagnostic(
                        code="composition.profile.override_conflict",
                        message=f"Override target '{override.target}' is defined by more than one profile",
                        path=("overrides", override.target),
                        profile=profile.name,
                        first_profile=override_sources[override.target],
                    )
                )
                continue
            override_sources[override.target] = profile.name
            merged_overrides.append(override)

    if diagnostics:
        return ProfileCompositionResult(
            status=RuntimeStatus.VALIDATION_ERROR,
            diagnostics=tuple(diagnostics),
            active_profiles=tuple(profile.name for profile in profiles),
            active_overrides=tuple(merged_overrides),
        )

    composed_name = name or "+".join(profile.name for profile in profiles) or "composed-profile"
    return ProfileCompositionResult(
        status=RuntimeStatus.OK,
        diagnostics=(),
        profile=Profile(
            name=composed_name,
            inputs=merged_inputs,
            checks=tuple(merged_checks),
            overrides=tuple(merged_overrides),
        ),
        active_profiles=tuple(profile.name for profile in profiles),
        active_overrides=tuple(merged_overrides),
    )


def apply_profile_to_workflow(workflow: Workflow, profile: Profile) -> WorkflowProfileApplicationResult:
    """Apply profile defaults to a workflow without silently overriding workflow intent."""

    diagnostics: list[Diagnostic] = []
    merged_inputs = dict(workflow.inputs)

    for key, value in profile.inputs.items():
        if key in merged_inputs and merged_inputs[key] != value:
            diagnostics.append(
                _diagnostic(
                    code="composition.workflow.input_conflict",
                    message=f"Profile input '{key}' would override explicit workflow input",
                    path=("inputs", key),
                    workflow=workflow.workflow,
                    profile=profile.name,
                    workflow_value=merged_inputs[key],
                    profile_value=value,
                )
            )
            continue
        merged_inputs.setdefault(key, value)

    if diagnostics:
        return WorkflowProfileApplicationResult(
            status=RuntimeStatus.VALIDATION_ERROR,
            diagnostics=tuple(diagnostics),
            active_profile=profile.name,
            active_overrides=profile.overrides,
        )

    return WorkflowProfileApplicationResult(
        status=RuntimeStatus.OK,
        workflow=Workflow(
            version=workflow.version,
            workflow=workflow.workflow,
            inputs=merged_inputs,
            state_needs=workflow.state_needs,
            state_bindings=workflow.state_bindings,
            states=workflow.states,
            step_results=workflow.step_results,
            blocks=workflow.blocks,
        ),
        active_profile=profile.name,
        active_overrides=profile.overrides,
    )


def _diagnostic(code: str, message: str, path: tuple[str, ...], **details: object) -> Diagnostic:
    return Diagnostic(code=code, level="error", message=message, path=path, details=details)
