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


def validate_workflow_input_allowed_values(workflow: Workflow, inputs: dict[str, object], *, code: str) -> tuple[Diagnostic, ...]:
    """Validate resolved input values against declared string enumerations."""

    diagnostics: list[Diagnostic] = []
    for name, declaration in workflow.declared_inputs.items():
        if not isinstance(name, str) or not isinstance(declaration, dict) or name not in inputs:
            continue
        allowed_values = declaration.get("allowed_values")
        if isinstance(allowed_values, list) and inputs[name] not in allowed_values:
            diagnostics.append(_diagnostic(
                code=code,
                message=f"Workflow input '{name}' must be one of its allowed_values",
                path=("inputs", name),
                workflow=workflow.workflow,
                input=name,
                value=inputs[name],
                allowed_values=allowed_values,
            ))
    return tuple(diagnostics)


def compose_profiles(*profiles: Profile, name: str | None = None) -> ProfileCompositionResult:
    """Compose profiles left-to-right without silent semantic mutation."""

    diagnostics: list[Diagnostic] = []
    merged_inputs: dict[str, object] = {}
    merged_working_directory: str | None = None
    merged_connectors: dict[str, object] = {}
    merged_checks: list[str] = []
    merged_overrides: list[Override] = []
    merged_launchers = {}
    input_sources: dict[str, str] = {}
    override_sources: dict[str, str] = {}
    launcher_sources: dict[str, str] = {}
    working_directory_source: str | None = None
    connector_sources: dict[tuple[str, str], str] = {}

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

        if profile.working_directory is not None:
            if merged_working_directory is not None and merged_working_directory != profile.working_directory:
                diagnostics.append(
                    _diagnostic(
                        code="composition.profile.working_directory_conflict",
                        message="Profile working_directory conflicts with an earlier profile value",
                        path=("working_directory",),
                        profile=profile.name,
                        first_profile=working_directory_source,
                        previous_value=merged_working_directory,
                        new_value=profile.working_directory,
                    )
                )
            elif merged_working_directory is None:
                merged_working_directory = profile.working_directory
                working_directory_source = profile.name

        for family, entry in profile.connectors.items():
            if not isinstance(family, str) or not isinstance(entry, dict):
                continue
            existing_entry = merged_connectors.get(family)
            if existing_entry is None:
                merged_connectors[family] = dict(entry)
                for field_name in entry:
                    if isinstance(field_name, str):
                        connector_sources[(family, field_name)] = profile.name
                continue
            if not isinstance(existing_entry, dict):
                continue
            for field_name, value in entry.items():
                if not isinstance(field_name, str):
                    continue
                if field_name in existing_entry and existing_entry[field_name] != value:
                    diagnostics.append(
                        _diagnostic(
                            code="composition.profile.connector_context_conflict",
                            message=f"Connector context field '{family}.{field_name}' conflicts with an earlier profile value",
                            path=("connectors", family, field_name),
                            profile=profile.name,
                            first_profile=connector_sources.get((family, field_name)),
                            previous_value=existing_entry[field_name],
                            new_value=value,
                        )
                    )
                    continue
                if field_name not in existing_entry:
                    existing_entry[field_name] = value
                    connector_sources[(family, field_name)] = profile.name

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

        for name, launcher in profile.launchers.items():
            if name in merged_launchers and merged_launchers[name] != launcher:
                diagnostics.append(
                    _diagnostic(
                        code="composition.profile.launcher_conflict",
                        message=f"Launcher '{name}' conflicts with an earlier profile definition",
                        path=("launchers", name),
                        profile=profile.name,
                        first_profile=launcher_sources[name],
                    )
                )
                continue
            if name not in merged_launchers:
                merged_launchers[name] = launcher
                launcher_sources[name] = profile.name

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
            working_directory=merged_working_directory,
            connectors=merged_connectors,
            checks=tuple(merged_checks),
            overrides=tuple(merged_overrides),
            launchers=merged_launchers,
        ),
        active_profiles=tuple(profile.name for profile in profiles),
        active_overrides=tuple(merged_overrides),
    )


def apply_profile_to_workflow(workflow: Workflow, profile: Profile) -> WorkflowProfileApplicationResult:
    """Apply profile defaults to a workflow without silently overriding workflow intent."""

    diagnostics: list[Diagnostic] = []
    merged_inputs = dict(workflow.inputs)
    protected_keys = set(workflow.protected_input_keys) | set(workflow.explicit_input_keys)

    for key, value in profile.inputs.items():
        if key in merged_inputs and merged_inputs[key] != value and key in protected_keys:
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
            profile=workflow.profile,
            inputs=merged_inputs,
            declared_inputs=workflow.declared_inputs,
            explicit_input_keys=workflow.explicit_input_keys,
            protected_input_keys=workflow.protected_input_keys,
            let_bindings=workflow.let_bindings,
            state_needs=workflow.state_needs,
            state_bindings=workflow.state_bindings,
            states=workflow.states,
            step_results=workflow.step_results,
            connector_contexts=profile.connectors,
            blocks=workflow.blocks,
            source_path=workflow.source_path,
            launch_dir=workflow.launch_dir,
            launch_profile_name=workflow.launch_profile_name,
            launch_profile_source=workflow.launch_profile_source,
            playbook_owned_pre_run=workflow.playbook_owned_pre_run,
        ),
        active_profile=profile.name,
        active_overrides=profile.overrides,
    )


def apply_profile_defaults_to_subsequent_steps(workflow: Workflow, profile: Profile) -> WorkflowProfileApplicationResult:
    """Apply profile missing-input defaults forward-only for subsequent execution."""

    return apply_runtime_profile_switch(workflow, profile)


def apply_runtime_profile_switch(workflow: Workflow, profile: Profile) -> WorkflowProfileApplicationResult:
    """Apply one runtime profile switch to workflow context for subsequent execution."""

    merged_inputs = dict(workflow.inputs)
    protected_keys = set(workflow.protected_input_keys) | set(workflow.explicit_input_keys)
    for key, value in profile.inputs.items():
        if key in protected_keys:
            continue
        merged_inputs[key] = value

    diagnostics = validate_workflow_input_allowed_values(
        workflow, merged_inputs, code="runtime.workflow.input_not_allowed",
    )
    if diagnostics:
        return WorkflowProfileApplicationResult(
            status=RuntimeStatus.VALIDATION_ERROR,
            diagnostics=diagnostics,
            active_profile=profile.name,
            active_overrides=profile.overrides,
        )

    return WorkflowProfileApplicationResult(
        status=RuntimeStatus.OK,
        workflow=Workflow(
            version=workflow.version,
            workflow=workflow.workflow,
            profile=workflow.profile,
            inputs=merged_inputs,
            declared_inputs=workflow.declared_inputs,
            explicit_input_keys=workflow.explicit_input_keys,
            protected_input_keys=workflow.protected_input_keys,
            let_bindings=workflow.let_bindings,
            state_needs=workflow.state_needs,
            state_bindings=workflow.state_bindings,
            states=workflow.states,
            step_results=workflow.step_results,
            connector_contexts=profile.connectors,
            blocks=workflow.blocks,
            source_path=workflow.source_path,
            launch_dir=workflow.launch_dir,
            launch_profile_name=workflow.launch_profile_name,
            launch_profile_source=workflow.launch_profile_source,
            playbook_owned_pre_run=workflow.playbook_owned_pre_run,
        ),
        active_profile=profile.name,
        active_overrides=profile.overrides,
    )


def should_ignore_runtime_profile_switch(workflow: Workflow, *, target_profile_name: str) -> bool:
    return (
        workflow.playbook_owned_pre_run
        and workflow.launch_profile_source == "explicit_cli"
        and isinstance(workflow.launch_profile_name, str)
        and bool(workflow.launch_profile_name)
        and workflow.launch_profile_name != target_profile_name
    )


def _diagnostic(code: str, message: str, path: tuple[str, ...], **details: object) -> Diagnostic:
    return Diagnostic(code=code, level="error", message=message, path=path, details=details)
