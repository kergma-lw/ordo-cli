"""Runtime-owned persistent state support."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONValue
from ordo.model.workflow import Workflow
from .state_paths import StatePathParseError, parse_state_path


@dataclass(frozen=True, slots=True)
class RuntimeStateError(Exception):
    """Structured runtime state error with a stable code."""

    code: str
    message: str
    details: JSONObject

    def to_diagnostic(self, *, path: tuple[str, ...] = ()) -> Diagnostic:
        return Diagnostic(
            code=self.code,
            level="error",
            message=self.message,
            path=path,
            details=dict(self.details),
        )


@dataclass(frozen=True, slots=True)
class StateLocation:
    """Resolved runtime state location."""

    name: str
    path: Path


@dataclass(frozen=True, slots=True)
class ResolvedStateTarget:
    """Resolved runtime state target ready for storage operations."""

    location: StateLocation
    key: str
    fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeStateRegistry:
    """Named runtime-managed state locations resolved for a workflow run."""

    locations: dict[str, StateLocation]

    @classmethod
    def from_workflow(cls, workflow: Workflow, *, base_dir: str | Path | None = None) -> "RuntimeStateRegistry":
        root = Path(base_dir) if base_dir is not None else Path.cwd()
        locations: dict[str, StateLocation] = {}
        for name, raw_location in workflow.states.items():
            if not isinstance(raw_location, str) or not raw_location:
                raise RuntimeStateError(
                    code="runtime.state.declaration_invalid",
                    message="Runtime state location must be a non-empty string",
                    details={"state": name, "actual_type": type(raw_location).__name__},
                )
            location_path = Path(raw_location)
            if not location_path.is_absolute():
                location_path = root / location_path
            locations[name] = StateLocation(name=name, path=location_path)
        return cls(locations=locations)

    def require(self, name: str) -> StateLocation:
        location = self.locations.get(name)
        if location is None:
            raise RuntimeStateError(
                code="runtime.state.declaration_missing",
                message=f"Runtime state '{name}' is not declared",
                details={"state": name},
            )
        return location


def read_state_document(location: StateLocation) -> JSONObject:
    """Return the plain-object state document for a declared location."""

    if not location.path.exists():
        return {}
    try:
        payload = json.loads(location.path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeStateError(
            code="runtime.state.read_failed",
            message="Reading runtime state file failed",
            details={"state": location.name, "path": str(location.path), "error": str(exc)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeStateError(
            code="runtime.state.invalid_json",
            message="Runtime state file did not contain valid JSON",
            details={"state": location.name, "path": str(location.path), "error": str(exc)},
        ) from exc
    return _validate_state_document(payload, location=location)


def resolve_state_target(expression: str, workflow: Workflow, *, base_dir: str | Path | None = None) -> ResolvedStateTarget:
    """Resolve a state path expression into a concrete storage target."""

    try:
        parsed = parse_state_path(expression)
    except StatePathParseError as exc:
        raise RuntimeStateError(
            code="runtime.state.path_invalid",
            message=exc.message,
            details={"expression": expression, "position": exc.position, "end": exc.end if exc.end is not None else exc.position},
        ) from exc

    key_value = resolve_workflow_input_reference(parsed.key_reference, workflow)
    if isinstance(key_value, dict) or isinstance(key_value, list):
        raise RuntimeStateError(
            code="runtime.state.key_invalid",
            message="Runtime state key reference must resolve to a scalar value",
            details={"expression": expression, "reference": ".".join(parsed.key_reference)},
        )

    state_name = workflow.state_bindings.get(parsed.state_role)
    if not isinstance(state_name, str) or not state_name:
        raise RuntimeStateError(
            code="runtime.state.binding_missing",
            message=f"Workflow logical state role '{parsed.state_role}' is not bound",
            details={"expression": expression, "role": parsed.state_role},
        )

    registry = RuntimeStateRegistry.from_workflow(workflow, base_dir=base_dir)
    return ResolvedStateTarget(
        location=registry.require(state_name),
        key=str(key_value),
        fields=parsed.fields,
    )


def write_state_document(location: StateLocation, document: JSONObject) -> None:
    """Persist a plain-object state document to a declared location."""

    _validate_state_document(document, location=location)
    try:
        location.path.parent.mkdir(parents=True, exist_ok=True)
        location.path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise RuntimeStateError(
            code="runtime.state.write_failed",
            message="Writing runtime state file failed",
            details={"state": location.name, "path": str(location.path), "error": str(exc)},
        ) from exc


def read_state_value(document: JSONObject, *, key: str, fields: tuple[str, ...] = ()) -> JSONValue | None:
    """Read a stored value from a plain-object state document."""

    if key not in document:
        return None
    current: JSONValue = document[key]
    for field in fields:
        if not isinstance(current, dict) or field not in current:
            return None
        current = current[field]
    return current


def write_state_value(document: JSONObject, *, key: str, fields: tuple[str, ...] = (), value: JSONValue) -> JSONObject:
    """Create or replace a stored value inside a plain-object state document."""

    if not fields:
        document[key] = value
        return document

    current = document.get(key)
    if current is None:
        current = {}
        document[key] = current
    if not isinstance(current, dict):
        current = {}
        document[key] = current

    node = current
    for field in fields[:-1]:
        child = node.get(field)
        if not isinstance(child, dict):
            child = {}
            node[field] = child
        node = child
    node[fields[-1]] = value
    return document


def delete_state_value(document: JSONObject, *, key: str, fields: tuple[str, ...] = ()) -> bool:
    """Delete a stored value from a plain-object state document."""

    if key not in document:
        return False
    if not fields:
        del document[key]
        return True

    current = document[key]
    if not isinstance(current, dict):
        return False

    node = current
    parents: list[tuple[dict[str, JSONValue], str]] = []
    for field in fields[:-1]:
        child = node.get(field)
        if not isinstance(child, dict):
            return False
        parents.append((node, field))
        node = child

    leaf = fields[-1]
    if leaf not in node:
        return False
    del node[leaf]

    while parents:
        parent, field = parents.pop()
        child = parent.get(field)
        if isinstance(child, dict) and not child:
            del parent[field]
            continue
        break

    if isinstance(document.get(key), dict) and not document[key]:
        del document[key]
    return True


def _validate_state_document(payload: JSONValue, *, location: StateLocation) -> JSONObject:
    if not isinstance(payload, dict):
        raise RuntimeStateError(
            code="runtime.state.invalid_shape",
            message="Runtime state file root must be an object",
            details={"state": location.name, "path": str(location.path), "actual_type": type(payload).__name__},
        )
    return dict(payload)


def resolve_workflow_input_reference(parts: tuple[str, ...], workflow: Workflow) -> JSONValue:
    """Resolve a dotted workflow input reference such as `inputs.task_key`."""

    if not parts or parts[0] != "inputs":
        reference = ".".join(parts) if parts else "<empty>"
        raise RuntimeStateError(
            code="runtime.state.reference_unknown",
            message=f"Unknown object '{parts[0]}'" if parts else "Unknown object",
            details={"reference": reference, "object": parts[0] if parts else None},
        )

    current: JSONValue = workflow.inputs
    for part in parts[1:]:
        if not isinstance(current, dict) or part not in current:
            raise RuntimeStateError(
                code="runtime.state.input_missing",
                message=f"Workflow input reference '{'.'.join(parts)}' is missing",
                details={"reference": ".".join(parts)},
            )
        current = current[part]
    return current
