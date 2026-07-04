"""YAML loading into canonical JSON-shaped models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONArray, JSONObject, JSONScalar, JSONValue
from ordo.model.profile import Override, Profile
from ordo.model.workflow import Guard, OperationRef, Step, Workflow


@dataclass(frozen=True, slots=True)
class LoadError(Exception):
    """Structured loader error suitable for diagnostics."""

    diagnostics: tuple[Diagnostic, ...]

    def __str__(self) -> str:
        return "; ".join(diagnostic.message for diagnostic in self.diagnostics)


def load_workflow_text(text: str, *, source: str = "<memory>") -> Workflow:
    """Load workflow YAML into the canonical typed model."""

    payload = load_yaml_document(text, source=source)
    if not isinstance(payload, dict):
        raise _load_error(
            code="load.workflow.root_type",
            message="Workflow root must be a mapping",
            path=(),
            details={"source": source, "actual_type": type(payload).__name__},
        )

    guards_data = _require_list(payload, "guards", source=source)
    steps_data = _require_list(payload, "steps", source=source)

    return Workflow(
        version=_require_int(payload, "version", source=source),
        workflow=_require_string(payload, "workflow", source=source),
        inputs=_optional_object(payload, "inputs", source=source),
        state_needs=_optional_object(payload, "state_needs", source=source),
        state_bindings=_optional_object(payload, "state_bindings", source=source),
        states=_optional_object(payload, "states", source=source),
        guards=tuple(_load_guard(item, index=index, source=source) for index, item in enumerate(guards_data)),
        steps=tuple(_load_step(item, index=index, source=source) for index, item in enumerate(steps_data)),
    )


def load_workflow_file(path: str | Path) -> Workflow:
    """Load workflow YAML from a file path."""

    source = str(path)
    return load_workflow_text(Path(path).read_text(encoding="utf-8"), source=source)


def load_profile_text(text: str, *, source: str = "<memory>") -> Profile:
    """Load profile YAML into the canonical typed model."""

    payload = load_yaml_document(text, source=source)
    if not isinstance(payload, dict):
        raise _load_error(
            code="load.profile.root_type",
            message="Profile root must be a mapping",
            path=(),
            details={"source": source, "actual_type": type(payload).__name__},
        )

    overrides_data = payload.get("overrides", [])
    if not isinstance(overrides_data, list):
        raise _load_error(
            code="load.profile.overrides_type",
            message="Profile overrides must be a list",
            path=("overrides",),
            details={"source": source, "actual_type": type(overrides_data).__name__},
        )

    checks_data = payload.get("checks", [])
    if not isinstance(checks_data, list):
        raise _load_error(
            code="load.profile.checks_type",
            message="Profile checks must be a list",
            path=("checks",),
            details={"source": source, "actual_type": type(checks_data).__name__},
        )

    return Profile(
        name=_require_string(payload, "name", source=source),
        inputs=_optional_object(payload, "inputs", source=source),
        checks=tuple(_require_string_item(item, path=("checks", str(index)), source=source) for index, item in enumerate(checks_data)),
        overrides=tuple(_load_override(item, index=index, source=source) for index, item in enumerate(overrides_data)),
    )


def load_profile_file(path: str | Path) -> Profile:
    """Load profile YAML from a file path."""

    source = str(path)
    return load_profile_text(Path(path).read_text(encoding="utf-8"), source=source)


def load_yaml_document(text: str, *, source: str = "<memory>") -> JSONValue:
    """Load YAML and normalize it into canonical JSON-shaped data."""

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        details: JSONObject = {"source": source}
        if mark is not None:
            details["line"] = mark.line + 1
            details["column"] = mark.column + 1
        raise _load_error(
            code="load.yaml.syntax",
            message="Invalid YAML document",
            path=(),
            details=details,
        ) from exc

    return _normalize_json_value(loaded, source=source, path=())


def _load_guard(payload: JSONValue, *, index: int, source: str) -> Guard:
    path = ("guards", str(index))
    if isinstance(payload, str):
        return Guard(expr=payload)

    data = _require_object(payload, path=path, source=source)
    return Guard(operation=_load_operation_ref(data, path=path, source=source))


def _load_step(payload: JSONValue, *, index: int, source: str) -> Step:
    path = ("steps", str(index))
    data = _require_object(payload, path=path, source=source)
    has_uses = "uses" in data
    has_state_set = "state_set" in data
    has_state_delete = "state_delete" in data
    if sum((has_uses, has_state_set, has_state_delete)) != 1:
        raise _load_error(
            code="load.step.form",
            message="Step must define exactly one of 'uses', 'state_set', or 'state_delete'",
            path=path,
            details={"source": source},
        )

    state_set = None
    if has_state_set:
        state_set = _require_object(data.get("state_set"), path=path + ("state_set",), source=source)

    state_delete = None
    if has_state_delete:
        state_delete = _require_string(data, "state_delete", path=path + ("state_delete",), source=source)

    return Step(
        name=_require_string(data, "name", path=path + ("name",), source=source),
        operation=_load_operation_ref(data, path=path, source=source) if has_uses else None,
        state_set=state_set,
        state_delete=state_delete,
        register=_optional_string(data, "register", path=path + ("register",), source=source),
    )


def _load_override(payload: JSONValue, *, index: int, source: str) -> Override:
    data = _require_object(payload, path=("overrides", str(index)), source=source)
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise _load_error(
            code="load.override.reason_type",
            message="Override reason must be a string when provided",
            path=("overrides", str(index), "reason"),
            details={"source": source, "actual_type": type(reason).__name__},
        )

    return Override(
        target=_require_string(data, "target", path=("overrides", str(index), "target"), source=source),
        with_=_optional_object(data, "with", path=("overrides", str(index), "with"), source=source),
        reason=reason,
    )


def _load_operation_ref(data: JSONObject, *, path: tuple[str, ...], source: str) -> OperationRef:
    with_payload = data.get("with", {})
    if not isinstance(with_payload, dict):
        raise _load_error(
            code="load.operation.with_type",
            message="Operation 'with' field must be an object",
            path=path + ("with",),
            details={"source": source, "actual_type": type(with_payload).__name__},
        )

    return OperationRef(
        uses=_require_string(data, "uses", path=path + ("uses",), source=source),
        with_=dict(with_payload),
    )


def _require_object(value: JSONValue, *, path: tuple[str, ...], source: str) -> JSONObject:
    if isinstance(value, dict):
        return value
    raise _load_error(
        code="load.shape.object_required",
        message="Expected object",
        path=path,
        details={"source": source, "actual_type": type(value).__name__},
    )


def _require_list(data: JSONObject, key: str, *, source: str) -> JSONArray:
    value = data.get(key)
    if isinstance(value, list):
        return value
    raise _load_error(
        code=f"load.{key}.type",
        message=f"Field '{key}' must be a list",
        path=(key,),
        details={"source": source, "actual_type": type(value).__name__},
    )


def _optional_object(
    data: JSONObject,
    key: str,
    *,
    path: tuple[str, ...] | None = None,
    source: str,
) -> JSONObject:
    value = data.get(key, {})
    if isinstance(value, dict):
        return dict(value)
    raise _load_error(
        code=f"load.{key}.type",
        message=f"Field '{key}' must be an object",
        path=path or (key,),
        details={"source": source, "actual_type": type(value).__name__},
    )


def _require_int(data: JSONObject, key: str, *, source: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _load_error(
            code=f"load.{key}.type",
            message=f"Field '{key}' must be an integer",
            path=(key,),
            details={"source": source, "actual_type": type(value).__name__},
        )
    return value


def _require_string(
    data: JSONObject,
    key: str,
    *,
    path: tuple[str, ...] | None = None,
    source: str,
) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise _load_error(
            code=f"load.{key}.type",
            message=f"Field '{key}' must be a string",
            path=path or (key,),
            details={"source": source, "actual_type": type(value).__name__},
        )
    return value


def _optional_string(
    data: JSONObject,
    key: str,
    *,
    path: tuple[str, ...] | None = None,
    source: str,
) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise _load_error(
        code=f"load.{key}.type",
        message=f"Field '{key}' must be a string",
        path=path or (key,),
        details={"source": source, "actual_type": type(value).__name__},
    )


def _require_string_item(value: JSONValue, *, path: tuple[str, ...], source: str) -> str:
    if isinstance(value, str):
        return value
    raise _load_error(
        code="load.checks.item_type",
        message="Check entries must be strings",
        path=path,
        details={"source": source, "actual_type": type(value).__name__},
    )


def _normalize_json_value(value: Any, *, source: str, path: tuple[str, ...]) -> JSONValue:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value

    if isinstance(value, list):
        return [_normalize_json_value(item, source=source, path=path + (str(index),)) for index, item in enumerate(value)]

    if isinstance(value, dict):
        normalized: JSONObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise _load_error(
                    code="load.json_key.type",
                    message="Object keys must be strings to remain JSON-shaped",
                    path=path,
                    details={"source": source, "actual_key_type": type(key).__name__},
                )
            normalized[key] = _normalize_json_value(item, source=source, path=path + (key,))
        return normalized

    raise _load_error(
        code="load.json_value.type",
        message="YAML value is not representable as canonical JSON-shaped data",
        path=path,
        details={"source": source, "actual_type": type(value).__name__},
    )


def _load_error(*, code: str, message: str, path: tuple[str, ...], details: JSONObject) -> LoadError:
    return LoadError(diagnostics=(Diagnostic(code=code, level="error", message=message, path=path, details=details),))
