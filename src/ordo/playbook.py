"""Project-local playbook discovery, loading, activation, and local-expression-aware working-directory resolution."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import os
from pathlib import Path
import yaml

from ordo.model.diagnostic import Diagnostic
from ordo.model.playbook_contract import PLAYBOOK_CONTRACT
from ordo.model.profile import Profile
from ordo.model.workflow import Step, StepBlock, Workflow
from ordo.runtime import LoadError, load_profile_file, load_workflow_document_file, load_workflow_text, load_yaml_document, validate_workflow_document, validate_workflow_semantics
from ordo.runtime.local_expression_contexts import LocalExpressionContext
from ordo.runtime.local_expressions import LOCAL_EXPRESSION_PARSE_ERRORS, evaluate_parsed_local_expression, parse_local_expression
from ordo.runtime.local_expression_engine.core import (
    BuiltinCallNode,
    FilterApplicationNode,
    LocalExpressionEvaluationError,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode,
    StepReferenceNode,
    ValueExpressionNode,
)


def _field_names(items: list[dict[str, object]]) -> frozenset[str]:
    return frozenset(item["name"] for item in items if isinstance(item.get("name"), str))


PLAYBOOK_VERSION = PLAYBOOK_CONTRACT["version"]
PLAYBOOK_DISCOVERY_PATH = PLAYBOOK_CONTRACT["discovery"]["path"]
PLAYBOOK_ALLOWED_FIELDS = _field_names(PLAYBOOK_CONTRACT["top_level_fields"])
DEFAULTS_ALLOWED_FIELDS = _field_names(PLAYBOOK_CONTRACT["defaults_fields"])
PROFILE_ENTRY_ALLOWED_FIELDS = _field_names(PLAYBOOK_CONTRACT["profile_entry_fields"])
STATE_ENTRY_ALLOWED_FIELDS = _field_names(PLAYBOOK_CONTRACT["state_entry_fields"])
WORKFLOW_ENTRY_ALLOWED_FIELDS = _field_names(PLAYBOOK_CONTRACT["workflow_entry_fields"])
PRE_RUN_ENTRY_ALLOWED_FIELDS = _field_names(PLAYBOOK_CONTRACT["pre_run_entry_fields"])


@dataclass(frozen=True, slots=True)
class PlaybookError(Exception):
    """Structured playbook activation error."""

    diagnostics: tuple[Diagnostic, ...]

    def __str__(self) -> str:
        return "; ".join(diagnostic.message for diagnostic in self.diagnostics)


@dataclass(frozen=True, slots=True)
class ActivatedPlaybook:
    """Resolved playbook activation context for one workflow run."""

    playbook_path: Path
    workflow_name: str
    workflow: Workflow
    workflow_path: Path
    workflow_description: str | None = None
    profile: Profile | None = None
    profile_path: Path | None = None
    available_profiles: dict[str, Profile] | None = None
    profile_working_directories: dict[str, Path | None] | None = None
    working_directory: Path | None = None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowCatalogInput:
    """Discovery metadata for one root-declared workflow input."""

    name: str
    description: str | None = None
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class PlaybookWorkflowCatalogEntry:
    """Discovery metadata for one playbook workflow entry."""

    playbook_path: Path
    workflow_name: str
    workflow_path: Path
    workflow_description: str | None = None
    working_directory: str | None = None
    inputs: tuple[WorkflowCatalogInput, ...] = ()


@dataclass(frozen=True, slots=True)
class PlaybookPreRunEntry:
    """Explicit playbook-owned launch-phase workflow entry."""

    file: str
    state_bindings: dict[str, str]
    states: dict[str, str]


@contextlib.contextmanager
def activated_working_directory(activated: ActivatedPlaybook):
    """Run inside the activated playbook working directory when one is set."""

    target = activated.working_directory
    if target is None:
        yield
        return

    previous = Path.cwd()
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(previous)


def discover_playbook_path(*, cwd: str | Path | None = None) -> Path:
    """Return the canonical Ordo project file path under the current working directory."""

    root = Path.cwd() if cwd is None else Path(cwd)
    candidate = root / PLAYBOOK_DISCOVERY_PATH
    if candidate.exists():
        return candidate
    raise _playbook_error(
        "playbook.discovery.missing",
        f"Ordo project file '{PLAYBOOK_DISCOVERY_PATH}' was not found in the current working directory",
        details={"cwd": str(root), "expected_path": str(candidate)},
    )


def list_playbook_workflows(*, playbook_path: str | Path | None = None, cwd: str | Path | None = None) -> tuple[PlaybookWorkflowCatalogEntry, ...]:
    """Return discovery metadata for all declared playbook workflows."""

    path = Path(playbook_path) if playbook_path is not None else discover_playbook_path(cwd=cwd)
    payload = _load_playbook_document(path)
    playbook_dir = path.parent
    workflows = _require_mapping(payload, "workflows", playbook_path=path)
    entries: list[PlaybookWorkflowCatalogEntry] = []
    for workflow_name in sorted(workflows):
        workflow_entry = workflows.get(workflow_name)
        if not isinstance(workflow_name, str) or not isinstance(workflow_entry, dict):
            continue
        _validate_workflow_entry_fields(workflow_entry, workflow_name=workflow_name, playbook_path=path)
        workflow_file = _require_string(workflow_entry, "file", playbook_path=path, path=("workflows", workflow_name, "file"))
        workflow_path = _resolve_catalog_file(playbook_dir=playbook_dir, default_subdir="workflows", raw=workflow_file)
        entries.append(
            PlaybookWorkflowCatalogEntry(
                playbook_path=path,
                workflow_name=workflow_name,
                workflow_path=workflow_path,
                workflow_description=_optional_non_empty_string(workflow_entry, "description"),
                working_directory=_optional_non_empty_string(workflow_entry, "working_directory"),
            )
        )
    return tuple(entries)


def inspect_playbook_workflow(
    workflow_name: str,
    *,
    playbook_path: str | Path | None = None,
    cwd: str | Path | None = None,
) -> PlaybookWorkflowCatalogEntry:
    """Return detailed discovery metadata for one playbook workflow entry."""

    path = Path(playbook_path) if playbook_path is not None else discover_playbook_path(cwd=cwd)
    payload = _load_playbook_document(path)
    playbook_dir = path.parent
    workflows = _require_mapping(payload, "workflows", playbook_path=path)
    workflow_entry = workflows.get(workflow_name)
    if not isinstance(workflow_entry, dict):
        raise _playbook_error(
            "playbook.workflow.missing",
            f"Workflow '{workflow_name}' is not declared in the playbook",
            path=("workflows", workflow_name),
            details={"playbook": str(path), "workflow": workflow_name},
        )
    _validate_workflow_entry_fields(workflow_entry, workflow_name=workflow_name, playbook_path=path)
    workflow_file = _require_string(workflow_entry, "file", playbook_path=path, path=("workflows", workflow_name, "file"))
    workflow_path = _resolve_catalog_file(playbook_dir=playbook_dir, default_subdir="workflows", raw=workflow_file)
    raw_workflow = _load_workflow_payload(workflow_path, launch_dir=Path.cwd() if cwd is None else Path(cwd))
    validation_report = validate_workflow_document(raw_workflow, source=str(workflow_path))
    if not validation_report.ok:
        raise PlaybookError(validation_report.diagnostics)
    compiled_workflow = _compile_workflow_payload(
        raw_workflow,
        workflow_name=workflow_name,
        workflow_entry=workflow_entry,
        playbook_payload=payload,
        playbook_dir=playbook_dir,
        playbook_path=path,
    )
    try:
        workflow = load_workflow_text(yaml.safe_dump(compiled_workflow, sort_keys=False), source=str(workflow_path))
    except LoadError as exc:
        raise PlaybookError(exc.diagnostics) from exc
    semantic_report = validate_workflow_semantics(workflow, source=str(workflow_path))
    if not semantic_report.ok:
        raise PlaybookError(semantic_report.diagnostics)
    return PlaybookWorkflowCatalogEntry(
        playbook_path=path,
        workflow_name=workflow_name,
        workflow_path=workflow_path,
        workflow_description=_optional_non_empty_string(workflow_entry, "description"),
        working_directory=_optional_non_empty_string(workflow_entry, "working_directory"),
        inputs=tuple(_catalog_input_from_declared_input(name, schema) for name, schema in workflow.declared_inputs.items() if isinstance(name, str)),
    )


def activate_playbook(
    *,
    workflow_name: str,
    profile_name: str | None = None,
    input_overrides: dict[str, object] | None = None,
    playbook_path: str | Path | None = None,
    cwd: str | Path | None = None,
) -> ActivatedPlaybook:
    """Load and activate one workflow from a playbook run."""

    path = Path(playbook_path) if playbook_path is not None else discover_playbook_path(cwd=cwd)
    payload = _load_playbook_document(path)
    playbook_dir = path.parent

    workflows = _require_mapping(payload, "workflows", playbook_path=path)
    workflow_entry = workflows.get(workflow_name)
    if not isinstance(workflow_entry, dict):
        raise _playbook_error(
            "playbook.workflow.missing",
            f"Workflow '{workflow_name}' is not declared in the playbook",
            path=("workflows", workflow_name),
            details={"playbook": str(path), "workflow": workflow_name},
        )
    _validate_workflow_entry_fields(workflow_entry, workflow_name=workflow_name, playbook_path=path)
    workflow_description = _optional_non_empty_string(workflow_entry, "description")

    workflow_file = _require_string(workflow_entry, "file", playbook_path=path, path=("workflows", workflow_name, "file"))
    workflow_path = _resolve_catalog_file(playbook_dir=playbook_dir, default_subdir="workflows", raw=workflow_file)

    active_profile_name = profile_name
    if active_profile_name is None:
        defaults = payload.get("defaults", {})
        if isinstance(defaults, dict):
            default_profile = defaults.get("profile")
            if isinstance(default_profile, str) and default_profile:
                active_profile_name = default_profile

    profile = None
    resolved_profile_path: Path | None = None
    available_profiles: dict[str, Profile] | None = None
    profile_working_directories: dict[str, Path | None] | None = None
    if active_profile_name is not None:
        profiles = _require_mapping(payload, "profiles", playbook_path=path, required=False)
        profile_entry = profiles.get(active_profile_name)
        if not isinstance(profile_entry, dict):
            raise _playbook_error(
                "playbook.profile.missing",
                f"Profile '{active_profile_name}' is not declared in the playbook",
                path=("profiles", active_profile_name),
                details={"playbook": str(path), "profile": active_profile_name},
            )
        profile_file = _require_string(profile_entry, "file", playbook_path=path, path=("profiles", active_profile_name, "file"))
        resolved_profile_path = _resolve_catalog_file(playbook_dir=playbook_dir, default_subdir="profiles", raw=profile_file)
        try:
            profile = load_profile_file(resolved_profile_path)
        except FileNotFoundError as exc:
            raise _playbook_error(
                "playbook.profile.file_missing",
                "Profile file referenced by the playbook does not exist",
                path=("profiles", active_profile_name, "file"),
                details={"playbook": str(path), "profile": active_profile_name, "profile_file": str(resolved_profile_path)},
            ) from exc
        except LoadError as exc:
            raise PlaybookError(exc.diagnostics) from exc

    raw_workflow = _load_workflow_payload(workflow_path, launch_dir=Path.cwd() if cwd is None else Path(cwd))
    validation_report = validate_workflow_document(raw_workflow, source=str(workflow_path))
    if not validation_report.ok:
        raise PlaybookError(validation_report.diagnostics)
    compiled_workflow = _compile_workflow_payload(
        raw_workflow,
        workflow_name=workflow_name,
        workflow_entry=workflow_entry,
        playbook_payload=payload,
        playbook_dir=playbook_dir,
        playbook_path=path,
    )
    try:
        workflow = load_workflow_text(yaml.safe_dump(compiled_workflow, sort_keys=False), source=str(workflow_path))
    except LoadError as exc:
        raise PlaybookError(exc.diagnostics) from exc

    workflow, profile = _apply_input_overrides(workflow, profile, input_overrides=input_overrides)
    workflow = _prepend_pre_run_workflows(
        workflow,
        playbook_payload=payload,
        playbook_dir=playbook_dir,
        playbook_path=path,
    )
    if _workflow_uses_profile_switch(workflow) or payload.get("pre_run") is not None:
        available_profiles = {}
        profile_working_directories = {}
        profiles = _require_mapping(payload, "profiles", playbook_path=path, required=False)
        for candidate_name, candidate_entry in profiles.items():
            if not isinstance(candidate_name, str) or not isinstance(candidate_entry, dict):
                continue
            candidate_file = _require_string(candidate_entry, "file", playbook_path=path, path=("profiles", candidate_name, "file"))
            candidate_path = _resolve_catalog_file(playbook_dir=playbook_dir, default_subdir="profiles", raw=candidate_file)
            try:
                candidate_profile = load_profile_file(candidate_path)
            except FileNotFoundError as exc:
                raise _playbook_error(
                    "playbook.profile.file_missing",
                    "Profile file referenced by the playbook does not exist",
                    path=("profiles", candidate_name, "file"),
                    details={"playbook": str(path), "profile": candidate_name, "profile_file": str(candidate_path)},
                ) from exc
            except LoadError as exc:
                raise PlaybookError(exc.diagnostics) from exc
            available_profiles[candidate_name] = candidate_profile
            profile_working_directories[candidate_name] = _resolve_profile_working_directory(
                candidate_name,
                candidate_profile,
                workflow=workflow,
                playbook_dir=playbook_dir,
                playbook_path=path,
            )
    working_directory = _resolve_working_directory(
        payload,
        workflow_entry,
        workflow_name=workflow_name,
        playbook_dir=playbook_dir,
        playbook_path=path,
        workflow=workflow,
        profile=profile,
        input_overrides=None,
    )
    workflow = _resolve_workflow_state_paths(workflow, base_dir=working_directory or playbook_dir)
    semantic_report = validate_workflow_semantics(workflow, source=str(workflow_path))
    if not semantic_report.ok:
        raise PlaybookError(semantic_report.diagnostics)
    activation_diagnostics = _activation_diagnostics(
        workflow_entry,
        workflow_name=workflow_name,
        playbook_path=path,
        workflow=workflow,
        working_directory=working_directory,
    )

    return ActivatedPlaybook(
        playbook_path=path,
        workflow_name=workflow_name,
        workflow=workflow,
        workflow_path=workflow_path,
        workflow_description=workflow_description,
        profile=profile,
        profile_path=resolved_profile_path,
        available_profiles=available_profiles,
        profile_working_directories=profile_working_directories,
        working_directory=working_directory,
        diagnostics=activation_diagnostics,
    )


def _apply_input_overrides(
    workflow: Workflow,
    profile: Profile | None,
    *,
    input_overrides: dict[str, object] | None,
) -> tuple[Workflow, Profile | None]:
    merged_workflow_inputs = dict(workflow.inputs)
    if profile is not None:
        for key, value in profile.inputs.items():
            merged_workflow_inputs.setdefault(key, value)
    if input_overrides:
        merged_workflow_inputs.update(input_overrides)

    _validate_activation_inputs(workflow, merged_workflow_inputs)

    overridden_workflow = Workflow(
        version=workflow.version,
        workflow=workflow.workflow,
        inputs=merged_workflow_inputs,
        declared_inputs=workflow.declared_inputs,
        state_needs=workflow.state_needs,
        state_bindings=workflow.state_bindings,
        states=workflow.states,
        step_results=workflow.step_results,
        blocks=workflow.blocks,
    )

    if profile is None:
        return overridden_workflow, None

    override_keys = set(input_overrides or {})
    remaining_profile_inputs = {key: value for key, value in profile.inputs.items() if key not in override_keys}
    if remaining_profile_inputs == profile.inputs:
        return overridden_workflow, profile

    overridden_profile = Profile(
        name=profile.name,
        inputs=remaining_profile_inputs,
        checks=profile.checks,
        overrides=profile.overrides,
        launchers=profile.launchers,
    )
    return overridden_workflow, overridden_profile


def _validate_activation_inputs(workflow: Workflow, inputs: dict[str, object]) -> None:
    declared_keys = set(workflow.declared_inputs)
    missing = sorted(key for key in declared_keys if key not in inputs)
    unknown = sorted(key for key in inputs if key not in declared_keys)
    diagnostics: list[Diagnostic] = []
    for key in missing:
        diagnostics.append(
            Diagnostic(
                code="playbook.workflow.input_missing",
                level="error",
                message=f"Workflow input '{key}' is required at activation time",
                path=("inputs", key),
                details={"workflow": workflow.workflow, "input": key},
            )
        )
    for key in unknown:
        diagnostics.append(
            Diagnostic(
                code="playbook.workflow.input_unknown",
                level="error",
                message=f"Workflow input '{key}' is not declared by the workflow",
                path=("inputs", key),
                details={"workflow": workflow.workflow, "input": key},
            )
        )
    if diagnostics:
        raise PlaybookError(tuple(diagnostics))


def _load_playbook_document(path: Path) -> dict[str, object]:
    try:
        payload = load_yaml_document(path.read_text(encoding="utf-8"), source=str(path))
    except FileNotFoundError as exc:
        raise _playbook_error(
            "playbook.discovery.file_missing",
            "Explicit playbook file does not exist",
            details={"playbook": str(path)},
        ) from exc
    except LoadError as exc:
        raise PlaybookError(exc.diagnostics) from exc

    if not isinstance(payload, dict):
        raise _playbook_error(
            "playbook.root_type",
            "Playbook root must be an object",
            details={"playbook": str(path), "actual_type": type(payload).__name__},
        )
    return payload


def _load_workflow_payload(path: Path, *, launch_dir: Path) -> dict[str, object]:
    try:
        payload = load_workflow_document_file(path, launch_dir=launch_dir)
    except FileNotFoundError as exc:
        raise _playbook_error(
            "playbook.workflow.file_missing",
            "Workflow file referenced by the playbook does not exist",
            details={"workflow_file": str(path)},
        ) from exc
    except LoadError as exc:
        raise PlaybookError(exc.diagnostics) from exc
    if not isinstance(payload, dict):
        raise _playbook_error(
            "playbook.workflow.root_type",
            "Workflow root must be an object",
            details={"workflow_file": str(path), "actual_type": type(payload).__name__},
        )
    return payload


def _compile_workflow_payload(
    raw_workflow: dict[str, object],
    *,
    workflow_name: str,
    workflow_entry: dict[str, object],
    playbook_payload: dict[str, object],
    playbook_dir: Path,
    playbook_path: Path,
) -> dict[str, object]:
    payload = dict(raw_workflow)
    state_needs = payload.get("state_needs")
    if not isinstance(state_needs, dict):
        return payload

    states_payload = _require_mapping(playbook_payload, "states", playbook_path=playbook_path)
    state_bindings = _require_mapping(workflow_entry, "state_bindings", playbook_path=playbook_path, path=("workflows", workflow_name, "state_bindings"), required=False)

    injected_states: dict[str, str] = {}
    role_to_state_name: dict[str, str] = {}
    for role_name in state_needs:
        if not isinstance(role_name, str) or not role_name:
            raise _playbook_error(
                "playbook.state_need.invalid",
                "Workflow state need name must be a non-empty string",
                details={"workflow": workflow_name},
            )
        target_name = state_bindings.get(role_name)
        if not isinstance(target_name, str) or not target_name:
            raise _playbook_error(
                "playbook.state_binding.missing",
                f"Workflow logical state role '{role_name}' has no playbook state binding",
                path=("workflows", workflow_name, "state_bindings", role_name),
                details={"workflow": workflow_name, "role": role_name, "playbook": str(playbook_path)},
            )
        state_entry = states_payload.get(target_name)
        if not isinstance(state_entry, dict):
            raise _playbook_error(
                "playbook.state_binding.target_missing",
                f"Playbook state binding '{target_name}' is not declared",
                path=("states", target_name),
                details={"workflow": workflow_name, "role": role_name, "state": target_name, "playbook": str(playbook_path)},
            )
        raw_path = state_entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise _playbook_error(
                "playbook.state.path_invalid",
                f"Playbook state '{target_name}' must declare a non-empty path",
                path=("states", target_name, "path"),
                details={"state": target_name, "playbook": str(playbook_path)},
            )
        injected_states[target_name] = raw_path
        role_to_state_name[role_name] = target_name

    extra_bindings = [name for name in state_bindings if name not in state_needs]
    if extra_bindings:
        raise _playbook_error(
            "playbook.state_binding.extra",
            "Playbook workflow entry declares extra state bindings for undeclared workflow logical state roles",
            path=("workflows", workflow_name, "state_bindings"),
            details={"workflow": workflow_name, "extra_bindings": extra_bindings, "playbook": str(playbook_path)},
        )

    payload["states"] = injected_states
    payload["state_bindings"] = role_to_state_name
    return payload


def _resolve_catalog_file(*, playbook_dir: Path, default_subdir: str, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    if "/" in raw:
        return playbook_dir / candidate
    return playbook_dir / default_subdir / candidate


def _prepend_pre_run_workflows(
    workflow: Workflow,
    *,
    playbook_payload: dict[str, object],
    playbook_dir: Path,
    playbook_path: Path,
) -> Workflow:
    raw_items = playbook_payload.get("pre_run")
    if raw_items is None:
        return workflow
    if not isinstance(raw_items, list):
        raise _playbook_error(
            "playbook.pre_run.invalid",
            "Playbook field 'pre_run' must be a list of workflow references",
            path=("pre_run",),
            details={"playbook": str(playbook_path), "actual_type": type(raw_items).__name__},
        )

    pre_run_blocks: list[StepBlock] = []
    states = _require_mapping(playbook_payload, "states", playbook_path=playbook_path, required=False)
    for index, item in enumerate(raw_items):
        entry = _parse_pre_run_entry(item, index=index, playbook_path=playbook_path, states=states)
        resolved = _resolve_catalog_file(playbook_dir=playbook_dir, default_subdir="workflows", raw=entry.file)
        if not resolved.exists():
            raise _playbook_error(
                "playbook.pre_run.file_missing",
                "Workflow file referenced by playbook pre_run does not exist",
                path=("pre_run", str(index)),
                details={"playbook": str(playbook_path), "workflow_file": str(resolved), "reference": entry.file},
            )
        pre_run_blocks.append(
            StepBlock(
                steps=(
                    Step(
                        name=f"pre_run[{index}]",
                        run=entry.file,
                        resolved_run_path=str(resolved.resolve()),
                        run_state_bindings=entry.state_bindings,
                        run_states=entry.states,
                    ),
                )
            )
        )

    return Workflow(
        version=workflow.version,
        workflow=workflow.workflow,
        inputs=workflow.inputs,
        declared_inputs=workflow.declared_inputs,
        state_needs=workflow.state_needs,
        state_bindings=workflow.state_bindings,
        states=workflow.states,
        step_results=workflow.step_results,
        blocks=tuple(pre_run_blocks) + workflow.blocks,
        source_path=workflow.source_path,
        launch_dir=workflow.launch_dir,
    )


def _parse_pre_run_entry(
    item: object,
    *,
    index: int,
    playbook_path: Path,
    states: dict[str, object],
) -> PlaybookPreRunEntry:
    if not isinstance(item, dict):
        raise _playbook_error(
            "playbook.pre_run.item_invalid",
            "Each playbook 'pre_run' item must be an object with an explicit workflow file",
            path=("pre_run", str(index)),
            details={"playbook": str(playbook_path), "actual_type": type(item).__name__},
        )
    for key in item:
        if key not in PRE_RUN_ENTRY_ALLOWED_FIELDS:
            raise _playbook_error(
                "playbook.pre_run.unknown_field",
                f"Unknown pre_run entry field '{key}'",
                path=("pre_run", str(index), key),
                details={"playbook": str(playbook_path), "allowed_fields": sorted(PRE_RUN_ENTRY_ALLOWED_FIELDS)},
            )
    file = _require_string(item, "file", playbook_path=playbook_path, path=("pre_run", str(index), "file"))
    raw_bindings = item.get("state_bindings")
    if raw_bindings is None:
        return PlaybookPreRunEntry(file=file, state_bindings={}, states={})
    if not isinstance(raw_bindings, dict):
        raise _playbook_error(
            "playbook.pre_run.state_bindings_invalid",
            "Pre-run entry field 'state_bindings' must be an object when present",
            path=("pre_run", str(index), "state_bindings"),
            details={"playbook": str(playbook_path), "actual_type": type(raw_bindings).__name__},
        )
    state_bindings: dict[str, str] = {}
    injected_states: dict[str, str] = {}
    for role_name, state_name in raw_bindings.items():
        if not isinstance(role_name, str) or not role_name or not isinstance(state_name, str) or not state_name:
            raise _playbook_error(
                "playbook.pre_run.state_binding_invalid",
                "Pre-run state bindings must map non-empty logical role names to non-empty playbook state names",
                path=("pre_run", str(index), "state_bindings"),
                details={"playbook": str(playbook_path), "role": role_name, "state": state_name},
            )
        if state_name not in states:
            raise _playbook_error(
                "playbook.pre_run.state_binding_target_missing",
                "Pre-run state binding must target an existing playbook state declaration",
                path=("pre_run", str(index), "state_bindings", role_name),
                details={"playbook": str(playbook_path), "role": role_name, "state": state_name},
            )
        state_entry = states[state_name]
        if not isinstance(state_entry, dict):
            raise _playbook_error(
                "playbook.pre_run.state_binding_target_invalid",
                "Pre-run state binding target must be a playbook state object",
                path=("pre_run", str(index), "state_bindings", role_name),
                details={"playbook": str(playbook_path), "role": role_name, "state": state_name},
            )
        raw_path = state_entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise _playbook_error(
                "playbook.pre_run.state_path_invalid",
                "Pre-run state binding target must declare a non-empty path",
                path=("states", state_name, "path"),
                details={"playbook": str(playbook_path), "role": role_name, "state": state_name},
            )
        resolved_path = Path(raw_path)
        if not resolved_path.is_absolute():
            resolved_path = playbook_path.parent / resolved_path
        state_bindings[role_name] = state_name
        injected_states[state_name] = str(resolved_path)
    return PlaybookPreRunEntry(file=file, state_bindings=state_bindings, states=injected_states)


def _require_mapping(
    payload: dict[str, object],
    key: str,
    *,
    playbook_path: Path,
    path: tuple[str, ...] | None = None,
    required: bool = True,
) -> dict[str, object]:
    value = payload.get(key)
    if value is None and not required:
        return {}
    if isinstance(value, dict):
        return value
    raise _playbook_error(
        "playbook.shape.mapping_required",
        f"Playbook field '{key}' must be an object",
        path=path or (key,),
        details={"playbook": str(playbook_path), "field": key, "actual_type": type(value).__name__},
    )


def _require_string(payload: dict[str, object], key: str, *, playbook_path: Path, path: tuple[str, ...]) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    raise _playbook_error(
        "playbook.shape.string_required",
        f"Playbook field '{key}' must be a non-empty string",
        path=path,
        details={"playbook": str(playbook_path), "field": key, "actual_type": type(value).__name__},
    )


def _playbook_error(code: str, message: str, *, path: tuple[str, ...] = (), details: dict[str, object] | None = None) -> PlaybookError:
    payload = {"stage": "activation", "category": _category_for_code(code), **(details or {})}
    return PlaybookError((Diagnostic(code=code, level="error", message=message, path=path, details=payload),))


def _validate_workflow_entry_fields(workflow_entry: dict[str, object], *, workflow_name: str, playbook_path: Path) -> None:
    if "profile" in workflow_entry:
        raise _playbook_error(
            "playbook.workflow.profile_field_forbidden",
            "Workflow entry field 'profile' is not allowed; active profile selection belongs to playbook run activation",
            path=("workflows", workflow_name, "profile"),
            details={"playbook": str(playbook_path), "workflow": workflow_name},
        )
    for key in workflow_entry:
        if key not in WORKFLOW_ENTRY_ALLOWED_FIELDS:
            raise _playbook_error(
                "playbook.workflow.unknown_field",
                f"Unknown workflow entry field '{key}'",
                path=("workflows", workflow_name, key),
                details={"playbook": str(playbook_path), "workflow": workflow_name, "allowed_fields": sorted(WORKFLOW_ENTRY_ALLOWED_FIELDS)},
            )
    description = workflow_entry.get("description")
    if description is not None and (not isinstance(description, str) or not description):
        raise _playbook_error(
            "playbook.workflow.description_invalid",
            "Workflow entry field 'description' must be a non-empty string when present",
            path=("workflows", workflow_name, "description"),
            details={"playbook": str(playbook_path), "workflow": workflow_name, "actual_type": type(description).__name__},
        )


def _optional_non_empty_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _catalog_input_from_declared_input(name: str, schema: object) -> WorkflowCatalogInput:
    description: str | None = None
    hint: str | None = None
    if isinstance(schema, dict):
        raw_description = schema.get("description")
        if isinstance(raw_description, str) and raw_description:
            description = raw_description
        raw_hint = schema.get("hint")
        if isinstance(raw_hint, str) and raw_hint:
            hint = raw_hint
    return WorkflowCatalogInput(name=name, description=description, hint=hint)


def _resolve_working_directory(
    playbook_payload: dict[str, object],
    workflow_entry: dict[str, object],
    *,
    workflow_name: str,
    playbook_dir: Path,
    playbook_path: Path,
    workflow: Workflow | None = None,
    profile: Profile | None = None,
    input_overrides: dict[str, object] | None = None,
) -> Path | None:
    defaults = playbook_payload.get("defaults")
    raw_value: object | None = None
    scope = "workflow"
    field_path = ("workflows", workflow_name, "working_directory")

    if isinstance(defaults, dict) and defaults.get("working_directory") is not None:
        raw_value = defaults.get("working_directory")
        scope = "defaults"
        field_path = ("defaults", "working_directory")
    if profile is not None and profile.working_directory is not None:
        raw_value = profile.working_directory
        scope = "profile"
        field_path = ("profiles", profile.name, "working_directory")
    if workflow_entry.get("working_directory") is not None:
        raw_value = workflow_entry.get("working_directory")
        scope = "workflow"
        field_path = ("workflows", workflow_name, "working_directory")

    if raw_value is None:
        return None
    if not isinstance(raw_value, str) or not raw_value:
        raise _playbook_error(
            _working_directory_code(scope, "invalid"),
            f"{_working_directory_label(scope, workflow_name=workflow_name, profile=profile)} must be a non-empty string",
            path=field_path,
            details={"playbook": str(playbook_path), "workflow": workflow_name, "actual_type": type(raw_value).__name__},
        )

    resolved_value = raw_value
    expression = _extract_value_expression(raw_value)
    if expression is not None:
        resolved_value = _evaluate_working_directory_expression(
            expression,
            scope=scope,
            field_path=field_path,
            workflow_name=workflow_name,
            playbook_path=playbook_path,
            workflow=workflow,
            profile=profile,
            input_overrides=input_overrides,
        )

    resolved = Path(resolved_value)
    if not resolved.is_absolute():
        resolved = playbook_dir / resolved
    resolved = resolved.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise _playbook_error(
            _working_directory_code(scope, "missing"),
            f"{_working_directory_label(scope, workflow_name=workflow_name, profile=profile)} must resolve to an existing directory",
            path=field_path,
            details={
                "playbook": str(playbook_path),
                "workflow": workflow_name,
                "working_directory": str(resolved),
            },
        )
    return resolved


def _extract_value_expression(value: str) -> str | None:
    if value.startswith("${") and value.endswith("}") and len(value) >= 4:
        return value[2:-1]
    return None


def _resolve_workflow_state_paths(workflow: Workflow, *, base_dir: Path) -> Workflow:
    resolved_states: dict[str, str] = {}
    for name, raw_location in workflow.states.items():
        location_path = Path(raw_location)
        if not location_path.is_absolute():
            location_path = base_dir / location_path
        resolved_states[name] = str(location_path.resolve())
    if resolved_states == workflow.states:
        return workflow
    return Workflow(
        version=workflow.version,
        workflow=workflow.workflow,
        inputs=workflow.inputs,
        declared_inputs=workflow.declared_inputs,
        state_needs=workflow.state_needs,
        state_bindings=workflow.state_bindings,
        states=resolved_states,
        step_results=workflow.step_results,
        blocks=workflow.blocks,
    )


def _activation_diagnostics(
    workflow_entry: dict[str, object],
    *,
    workflow_name: str,
    playbook_path: Path,
    workflow: Workflow,
    working_directory: Path | None,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    has_state_bindings = isinstance(workflow_entry.get("state_bindings"), dict) and bool(workflow_entry.get("state_bindings"))
    if has_state_bindings and working_directory is None:
        diagnostics.append(
            Diagnostic(
                code="playbook.workflow.working_directory_recommended_for_state",
                level="warning",
                message="Workflow entry binds runtime state but does not declare working_directory; relative state paths resolve from the playbook directory",
                path=("workflows", workflow_name),
                details={
                    "stage": "activation",
                    "category": "working_directory",
                    "playbook": str(playbook_path),
                    "workflow": workflow.workflow,
                },
            )
        )
    return tuple(diagnostics)


def _evaluate_working_directory_expression(
    expression: str,
    *,
    scope: str,
    field_path: tuple[str, ...],
    workflow_name: str,
    playbook_path: Path,
    workflow: Workflow | None,
    profile: Profile | None,
    input_overrides: dict[str, object] | None,
) -> str:
    try:
        parsed = parse_local_expression(expression, context=LocalExpressionContext.EMBEDDED_VALUE)
    except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
        raise _playbook_error(
            _working_directory_code(scope, "expression_syntax"),
            exc.message,
            path=field_path,
            details={
                "playbook": str(playbook_path),
                "workflow": workflow_name,
                "expression": expression,
                "position": exc.position,
                "end": exc.end if exc.end is not None else exc.position,
            },
        ) from exc

    invalid = _validate_working_directory_expression(parsed)
    if invalid is not None:
        code, message, details = invalid
        raise _playbook_error(
            _working_directory_scope_code(scope, code),
            message,
            path=field_path,
            details={"playbook": str(playbook_path), "workflow": workflow_name, "expression": expression, **details},
        )

    activation_workflow = _working_directory_activation_workflow(workflow=workflow, profile=profile, input_overrides=input_overrides)
    try:
        value = evaluate_parsed_local_expression(parsed, activation_workflow, step_results={})
    except LocalExpressionEvaluationError as exc:
        raise _playbook_error(
            _working_directory_code(scope, "expression_invalid"),
            exc.message,
            path=field_path,
            details={"playbook": str(playbook_path), "workflow": workflow_name, "expression": expression, **exc.details},
        ) from exc

    if not isinstance(value, str) or not value:
        raise _playbook_error(
            _working_directory_code(scope, "expression_type"),
            f"{_working_directory_label(scope, workflow_name=workflow_name, profile=profile)} expression must resolve to a non-empty string",
            path=field_path,
            details={
                "playbook": str(playbook_path),
                "workflow": workflow_name,
                "expression": expression,
                "actual_type": type(value).__name__,
            },
        )
    return value


def _working_directory_activation_workflow(
    *,
    workflow: Workflow | None,
    profile: Profile | None,
    input_overrides: dict[str, object] | None,
) -> Workflow:
    merged_inputs: dict[str, object] = {}
    if workflow is not None:
        merged_inputs.update(workflow.inputs)
    if profile is not None:
        for key, value in profile.inputs.items():
            merged_inputs.setdefault(key, value)
    if input_overrides:
        merged_inputs.update(input_overrides)

    template = workflow
    if template is None:
        return Workflow(version=0, workflow="activation", inputs=merged_inputs, state_needs={}, state_bindings={}, states={}, step_results={}, blocks=())

    return Workflow(
        version=template.version,
        workflow=template.workflow,
        inputs=merged_inputs,
        declared_inputs=template.declared_inputs,
        state_needs=template.state_needs,
        state_bindings=template.state_bindings,
        states=template.states,
        step_results={},
        blocks=template.blocks,
    )


def _validate_working_directory_expression(parsed) -> tuple[str, str, dict[str, object]] | None:
    root = parsed.value.root if getattr(parsed, "value", None) is not None else parsed.root

    def visit(node: ValueExpressionNode) -> tuple[str, str, dict[str, object]] | None:
        if isinstance(node, ReferenceNode):
            if len(node.parts) < 2 or node.parts[0] != "inputs":
                return (
                    "working_directory_expression_root",
                    "Working-directory expression may read only dotted inputs references",
                    {"reference": ".".join(node.parts)},
                )
            return None
        if isinstance(node, StateReferenceNode):
            return (
                "working_directory_expression_state_forbidden",
                "Working-directory expression must not read runtime state",
                {"reference": parsed.source[node.start : node.end]},
            )
        if isinstance(node, StepReferenceNode):
            return (
                "working_directory_expression_step_forbidden",
                "Working-directory expression must not read registered step results",
                {"reference": parsed.source[node.start : node.end]},
            )
        if isinstance(node, PipelineNode):
            invalid = visit(node.source)
            if invalid is not None:
                return invalid
            for filter_node in node.filters:
                invalid = visit(filter_node)
                if invalid is not None:
                    return invalid
            return None
        if isinstance(node, BuiltinCallNode):
            for argument in node.arguments:
                invalid = visit(argument)
                if invalid is not None:
                    return invalid
            return None
        if isinstance(node, FilterApplicationNode):
            for argument in node.arguments:
                invalid = visit(argument)
                if invalid is not None:
                    return invalid
            return None
        return None

    return visit(root)


def _category_for_code(code: str) -> str:
    if code.startswith("playbook.discovery."):
        return "discovery"
    if code.startswith("playbook.workflow."):
        return "workflow"
    if code.startswith("playbook.profile."):
        return "profile"
    if code.startswith("playbook.defaults.") or code.startswith("playbook.working_directory."):
        return "working_directory"
    if code.startswith("playbook.state_binding.") or code.startswith("playbook.state_need.") or code.startswith("playbook.state."):
        return "state_binding"
    return "shape"


def _working_directory_label(scope: str, *, workflow_name: str, profile: Profile | None) -> str:
    if scope == "defaults":
        return "Playbook defaults field 'working_directory'"
    if scope == "profile":
        profile_name = profile.name if profile is not None else "<profile>"
        return f"Profile '{profile_name}' field 'working_directory'"
    return "Workflow entry field 'working_directory'"


def _working_directory_code(scope: str, suffix: str) -> str:
    if scope == "defaults":
        return f"playbook.defaults.working_directory_{suffix}"
    if scope == "profile":
        return f"playbook.profile.working_directory_{suffix}"
    return f"playbook.workflow.working_directory_{suffix}"


def _working_directory_scope_code(scope: str, generic_code: str) -> str:
    if not generic_code.startswith("working_directory_"):
        return generic_code
    return _working_directory_code(scope, generic_code.removeprefix("working_directory_"))


def _resolve_profile_working_directory(
    profile_name: str,
    profile: Profile,
    *,
    workflow: Workflow,
    playbook_dir: Path,
    playbook_path: Path,
) -> Path | None:
    raw_value = profile.working_directory
    if raw_value is None:
        return None
    profile_inputs = dict(workflow.inputs)
    profile_inputs.update(profile.inputs)
    activation_workflow = Workflow(
        version=workflow.version,
        workflow=workflow.workflow,
        inputs=profile_inputs,
        declared_inputs=workflow.declared_inputs,
        state_needs=workflow.state_needs,
        state_bindings=workflow.state_bindings,
        states=workflow.states,
        step_results=workflow.step_results,
        blocks=workflow.blocks,
        source_path=workflow.source_path,
        launch_dir=workflow.launch_dir,
    )
    resolved_value = raw_value
    expression = _extract_value_expression(raw_value)
    if expression is not None:
        resolved_value = _evaluate_working_directory_expression(
            expression,
            scope="profile",
            field_path=("profiles", profile_name, "working_directory"),
            workflow_name=workflow.workflow,
            playbook_path=playbook_path,
            workflow=activation_workflow,
            profile=profile,
            input_overrides=None,
        )
    resolved = Path(resolved_value)
    if not resolved.is_absolute():
        resolved = playbook_dir / resolved
    resolved = resolved.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise _playbook_error(
            "playbook.profile.working_directory_missing",
            f"Profile '{profile_name}' field 'working_directory' must resolve to an existing directory",
            path=("profiles", profile_name, "working_directory"),
            details={"playbook": str(playbook_path), "profile": profile_name, "working_directory": str(resolved)},
        )
    return resolved


def _workflow_uses_profile_switch(workflow: Workflow) -> bool:
    return any(step.profile_switch is not None for step in workflow.steps)
