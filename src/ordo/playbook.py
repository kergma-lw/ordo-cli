"""Project-local playbook discovery, loading, and workflow activation."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import os
from pathlib import Path
import yaml

from ordo.model.diagnostic import Diagnostic
from ordo.model.playbook_contract import PLAYBOOK_CONTRACT
from ordo.model.profile import Profile
from ordo.model.workflow import Workflow
from ordo.runtime import LoadError, load_profile_file, load_workflow_text, load_yaml_document
from ordo.runtime.value_expressions import (
    BuiltinCallNode,
    FilterApplicationNode,
    ParsedValueExpression,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode,
    StepReferenceNode,
    ValueExpressionEvaluationError,
    ValueExpressionNode,
    ValueExpressionParseError,
    evaluate_value_expression,
    parse_value_expression,
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
    profile: Profile | None = None
    profile_path: Path | None = None
    working_directory: Path | None = None


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
    """Return the canonical playbook path under the current working directory."""

    root = Path.cwd() if cwd is None else Path(cwd)
    candidate = root / PLAYBOOK_DISCOVERY_PATH
    if candidate.exists():
        return candidate
    raise _playbook_error(
        "playbook.discovery.missing",
        f"Playbook file '{PLAYBOOK_DISCOVERY_PATH}' was not found in the current working directory",
        details={"cwd": str(root), "expected_path": str(candidate)},
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

    raw_workflow = _load_workflow_payload(workflow_path)
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
    working_directory = _resolve_working_directory(
        workflow_entry,
        workflow_name=workflow_name,
        playbook_dir=playbook_dir,
        playbook_path=path,
        workflow=workflow,
        profile=profile,
        input_overrides=None,
    )

    return ActivatedPlaybook(
        playbook_path=path,
        workflow_name=workflow_name,
        workflow=workflow,
        workflow_path=workflow_path,
        profile=profile,
        profile_path=resolved_profile_path,
        working_directory=working_directory,
    )


def _apply_input_overrides(
    workflow: Workflow,
    profile: Profile | None,
    *,
    input_overrides: dict[str, object] | None,
) -> tuple[Workflow, Profile | None]:
    if not input_overrides:
        return workflow, profile

    merged_workflow_inputs = dict(workflow.inputs)
    merged_workflow_inputs.update(input_overrides)
    overridden_workflow = Workflow(
        version=workflow.version,
        workflow=workflow.workflow,
        inputs=merged_workflow_inputs,
        state_needs=workflow.state_needs,
        state_bindings=workflow.state_bindings,
        states=workflow.states,
        step_results=workflow.step_results,
        blocks=workflow.blocks,
    )

    if profile is None:
        return overridden_workflow, None

    remaining_profile_inputs = {key: value for key, value in profile.inputs.items() if key not in input_overrides}
    if remaining_profile_inputs == profile.inputs:
        return overridden_workflow, profile

    overridden_profile = Profile(
        name=profile.name,
        inputs=remaining_profile_inputs,
        checks=profile.checks,
        overrides=profile.overrides,
    )
    return overridden_workflow, overridden_profile


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


def _load_workflow_payload(path: Path) -> dict[str, object]:
    try:
        payload = load_yaml_document(path.read_text(encoding="utf-8"), source=str(path))
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
        resolved_path = Path(raw_path)
        if not resolved_path.is_absolute():
            resolved_path = playbook_dir / resolved_path
        injected_states[target_name] = str(resolved_path)
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


def _resolve_working_directory(
    workflow_entry: dict[str, object],
    *,
    workflow_name: str,
    playbook_dir: Path,
    playbook_path: Path,
    workflow: Workflow | None = None,
    profile: Profile | None = None,
    input_overrides: dict[str, object] | None = None,
) -> Path | None:
    raw_value = workflow_entry.get("working_directory")
    if raw_value is None:
        return None
    if not isinstance(raw_value, str) or not raw_value:
        raise _playbook_error(
            "playbook.workflow.working_directory_invalid",
            "Workflow entry field 'working_directory' must be a non-empty string",
            path=("workflows", workflow_name, "working_directory"),
            details={"playbook": str(playbook_path), "workflow": workflow_name, "actual_type": type(raw_value).__name__},
        )

    resolved_value = raw_value
    expression = _extract_value_expression(raw_value)
    if expression is not None:
        resolved_value = _evaluate_working_directory_expression(
            expression,
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
            "playbook.workflow.working_directory_missing",
            "Workflow entry working_directory must resolve to an existing directory",
            path=("workflows", workflow_name, "working_directory"),
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


def _evaluate_working_directory_expression(
    expression: str,
    *,
    workflow_name: str,
    playbook_path: Path,
    workflow: Workflow | None,
    profile: Profile | None,
    input_overrides: dict[str, object] | None,
) -> str:
    try:
        parsed = parse_value_expression(expression)
    except ValueExpressionParseError as exc:
        raise _playbook_error(
            "playbook.workflow.working_directory_expression_syntax",
            exc.message,
            path=("workflows", workflow_name, "working_directory"),
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
            code,
            message,
            path=("workflows", workflow_name, "working_directory"),
            details={"playbook": str(playbook_path), "workflow": workflow_name, "expression": expression, **details},
        )

    activation_workflow = _working_directory_activation_workflow(workflow=workflow, profile=profile, input_overrides=input_overrides)
    try:
        value = evaluate_value_expression(parsed, activation_workflow, step_results={})
    except ValueExpressionEvaluationError as exc:
        raise _playbook_error(
            "playbook.workflow.working_directory_expression_invalid",
            exc.message,
            path=("workflows", workflow_name, "working_directory"),
            details={"playbook": str(playbook_path), "workflow": workflow_name, "expression": expression, **exc.details},
        ) from exc

    if not isinstance(value, str) or not value:
        raise _playbook_error(
            "playbook.workflow.working_directory_expression_type",
            "Workflow entry working_directory expression must resolve to a non-empty string",
            path=("workflows", workflow_name, "working_directory"),
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
        state_needs=template.state_needs,
        state_bindings=template.state_bindings,
        states=template.states,
        step_results={},
        blocks=template.blocks,
    )


def _validate_working_directory_expression(parsed: ParsedValueExpression) -> tuple[str, str, dict[str, object]] | None:
    def visit(node: ValueExpressionNode) -> tuple[str, str, dict[str, object]] | None:
        if isinstance(node, ReferenceNode):
            if len(node.parts) < 2 or node.parts[0] != "inputs":
                return (
                    "playbook.workflow.working_directory_expression_root",
                    "Workflow entry working_directory expression may read only dotted inputs references",
                    {"reference": ".".join(node.parts)},
                )
            return None
        if isinstance(node, StateReferenceNode):
            return (
                "playbook.workflow.working_directory_expression_state_forbidden",
                "Workflow entry working_directory expression must not read runtime state",
                {"reference": parsed.source[node.start : node.end]},
            )
        if isinstance(node, StepReferenceNode):
            return (
                "playbook.workflow.working_directory_expression_step_forbidden",
                "Workflow entry working_directory expression must not read registered step results",
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

    return visit(parsed.root)


def _category_for_code(code: str) -> str:
    if code.startswith("playbook.discovery."):
        return "discovery"
    if code.startswith("playbook.workflow."):
        return "workflow"
    if code.startswith("playbook.profile."):
        return "profile"
    if code.startswith("playbook.state_binding.") or code.startswith("playbook.state_need.") or code.startswith("playbook.state."):
        return "state_binding"
    return "shape"
