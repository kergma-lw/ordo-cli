"""Project-local routine registry discovery, validation, and loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.routine_contract import ROUTINE_CONTRACT
from ordo.runtime.loading import LoadError, load_yaml_document
import yaml


def _field_names(items: list[dict[str, object]]) -> frozenset[str]:
    return frozenset(item["name"] for item in items if isinstance(item.get("name"), str))


ROUTINE_REGISTRY_VERSION = ROUTINE_CONTRACT["version"]
ROUTINE_REGISTRY_DISCOVERY_PATH = ROUTINE_CONTRACT["discovery"]["path"]
ROUTINE_REGISTRY_ALLOWED_FIELDS = _field_names(ROUTINE_CONTRACT["top_level_fields"])
ROUTINE_ENTRY_ALLOWED_FIELDS = _field_names(ROUTINE_CONTRACT["routine_entry_fields"])
ROUTINE_IMPLEMENTATION_ALLOWED_FIELDS = _field_names(ROUTINE_CONTRACT["implementation_fields"])


@dataclass(frozen=True, slots=True)
class RoutineRegistryError(Exception):
    """Structured routine-registry loading error."""

    diagnostics: tuple[Diagnostic, ...]

    def __str__(self) -> str:
        return "; ".join(diagnostic.message for diagnostic in self.diagnostics)


@dataclass(frozen=True, slots=True)
class RoutineArg:
    """Declared routine argument contract."""

    type_name: str
    required: bool = False


@dataclass(frozen=True, slots=True)
class RoutineImplementation:
    """Bounded routine implementation entry."""

    argv: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoutineEntry:
    """One declared project-local routine entry."""

    id: str
    kind: str
    summary: str
    args: dict[str, RoutineArg] = field(default_factory=dict)
    implementation: RoutineImplementation = field(default_factory=lambda: RoutineImplementation(argv=()))
    failure_modes: tuple[str, ...] = ()
    outputs: dict[str, object] = field(default_factory=dict)
    log_hints: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RoutineRegistry:
    """Loaded routine-registry catalog."""

    path: Path
    routines: dict[str, RoutineEntry]


def discover_routine_registry_path(*, cwd: str | Path | None = None) -> Path:
    """Return the canonical routine-registry path under the current working directory."""

    root = Path.cwd() if cwd is None else Path(cwd)
    candidate = root / ROUTINE_REGISTRY_DISCOVERY_PATH
    if candidate.exists():
        return candidate
    raise _routine_error(
        "routine.discovery.missing",
        f"Routine registry '{ROUTINE_REGISTRY_DISCOVERY_PATH}' was not found in the current working directory",
        details={"cwd": str(root), "expected_path": str(candidate)},
    )


def load_routine_registry(*, path: str | Path | None = None, cwd: str | Path | None = None) -> RoutineRegistry:
    """Load and validate one routine registry."""

    registry_path = Path(path) if path is not None else discover_routine_registry_path(cwd=cwd)
    try:
        text = registry_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise _routine_error(
            "routine.discovery.missing",
            "Routine registry file does not exist",
            details={"path": str(registry_path)},
        ) from exc
    _detect_duplicate_routine_ids(text, source=str(registry_path))
    try:
        payload = load_yaml_document(text, source=str(registry_path))
    except LoadError as exc:
        raise RoutineRegistryError(exc.diagnostics) from exc

    if not isinstance(payload, dict):
        raise _routine_error(
            "routine.registry.root_type",
            "Routine registry root must be an object",
            details={"path": str(registry_path), "actual_type": type(payload).__name__},
        )

    _validate_unknown_fields(payload, ROUTINE_REGISTRY_ALLOWED_FIELDS, source=str(registry_path), path=())
    version = payload.get("version")
    if version != ROUTINE_REGISTRY_VERSION:
        raise _routine_error(
            "routine.registry.version",
            f"Routine registry version must be {ROUTINE_REGISTRY_VERSION}",
            path=("version",),
            details={"path": str(registry_path), "actual": version},
        )

    routines_payload = payload.get("routines")
    if not isinstance(routines_payload, dict):
        raise _routine_error(
            "routine.registry.routines_type",
            "Routine registry field 'routines' must be an object",
            path=("routines",),
            details={"path": str(registry_path), "actual_type": type(routines_payload).__name__},
        )

    routines: dict[str, RoutineEntry] = {}
    for routine_id, entry_payload in routines_payload.items():
        if not isinstance(routine_id, str) or not routine_id:
            raise _routine_error(
                "routine.registry.id",
                "Routine identifiers must be non-empty strings",
                path=("routines", str(routine_id)),
                details={"path": str(registry_path)},
            )
        if routine_id in routines:
            raise _routine_error(
                "routine.registry.duplicate_id",
                f"Routine '{routine_id}' is declared more than once",
                path=("routines", routine_id),
                details={"path": str(registry_path), "id": routine_id},
            )
        if not isinstance(entry_payload, dict):
            raise _routine_error(
                "routine.registry.entry_type",
                "Routine entry must be an object",
                path=("routines", routine_id),
                details={"path": str(registry_path), "id": routine_id, "actual_type": type(entry_payload).__name__},
            )
        routines[routine_id] = _load_routine_entry(entry_payload, routine_id=routine_id, registry_path=registry_path)
    return RoutineRegistry(path=registry_path, routines=routines)


def _load_routine_entry(entry_payload: dict[str, object], *, routine_id: str, registry_path: Path) -> RoutineEntry:
    _validate_unknown_fields(entry_payload, ROUTINE_ENTRY_ALLOWED_FIELDS, source=str(registry_path), path=("routines", routine_id))
    kind = _require_non_empty_string(entry_payload, "kind", registry_path=registry_path, path=("routines", routine_id, "kind"))
    summary = _require_non_empty_string(entry_payload, "summary", registry_path=registry_path, path=("routines", routine_id, "summary"))
    args_payload = entry_payload.get("args", {})
    if not isinstance(args_payload, dict):
        raise _routine_error(
            "routine.registry.args_type",
            "Routine field 'args' must be an object when present",
            path=("routines", routine_id, "args"),
            details={"path": str(registry_path), "id": routine_id, "actual_type": type(args_payload).__name__},
        )
    args: dict[str, RoutineArg] = {}
    for arg_name, arg_payload in args_payload.items():
        if not isinstance(arg_name, str) or not arg_name:
            raise _routine_error(
                "routine.registry.arg_name",
                "Routine argument names must be non-empty strings",
                path=("routines", routine_id, "args", str(arg_name)),
                details={"path": str(registry_path), "id": routine_id},
            )
        if not isinstance(arg_payload, dict):
            raise _routine_error(
                "routine.registry.arg_type",
                "Routine argument declarations must be objects",
                path=("routines", routine_id, "args", arg_name),
                details={"path": str(registry_path), "id": routine_id, "actual_type": type(arg_payload).__name__},
            )
        type_name = _require_non_empty_string(arg_payload, "type", registry_path=registry_path, path=("routines", routine_id, "args", arg_name, "type"))
        required = arg_payload.get("required", False)
        if not isinstance(required, bool):
            raise _routine_error(
                "routine.registry.arg_required_type",
                "Routine argument field 'required' must be a boolean when present",
                path=("routines", routine_id, "args", arg_name, "required"),
                details={"path": str(registry_path), "id": routine_id, "arg": arg_name, "actual_type": type(required).__name__},
            )
        args[arg_name] = RoutineArg(type_name=type_name, required=required)
    implementation = _load_routine_implementation(entry_payload.get("implementation"), routine_id=routine_id, registry_path=registry_path)
    failure_modes = _require_non_empty_string_array(entry_payload.get("failure_modes"), routine_id=routine_id, registry_path=registry_path)
    outputs = _optional_object(entry_payload, "outputs", routine_id=routine_id, registry_path=registry_path)
    log_hints = _optional_object(entry_payload, "log_hints", routine_id=routine_id, registry_path=registry_path)
    return RoutineEntry(
        id=routine_id,
        kind=kind,
        summary=summary,
        args=args,
        implementation=implementation,
        failure_modes=failure_modes,
        outputs=outputs,
        log_hints=log_hints,
    )


def _load_routine_implementation(value: object, *, routine_id: str, registry_path: Path) -> RoutineImplementation:
    if not isinstance(value, dict):
        raise _routine_error(
            "routine.registry.implementation_type",
            "Routine field 'implementation' must be an object",
            path=("routines", routine_id, "implementation"),
            details={"path": str(registry_path), "id": routine_id, "actual_type": type(value).__name__},
        )
    _validate_unknown_fields(value, ROUTINE_IMPLEMENTATION_ALLOWED_FIELDS, source=str(registry_path), path=("routines", routine_id, "implementation"))
    argv = value.get("argv")
    if not isinstance(argv, list) or not argv:
        raise _routine_error(
            "routine.registry.argv_type",
            "Routine implementation field 'argv' must be a non-empty array",
            path=("routines", routine_id, "implementation", "argv"),
            details={"path": str(registry_path), "id": routine_id, "actual_type": type(argv).__name__},
        )
    normalized: list[str] = []
    for index, item in enumerate(argv):
        if not isinstance(item, str) or not item:
            raise _routine_error(
                "routine.registry.argv_item_type",
                "Routine implementation argv items must be non-empty strings",
                path=("routines", routine_id, "implementation", "argv", str(index)),
                details={"path": str(registry_path), "id": routine_id, "actual_type": type(item).__name__},
            )
        normalized.append(item)
    return RoutineImplementation(argv=tuple(normalized))


def _optional_object(payload: dict[str, object], key: str, *, routine_id: str, registry_path: Path) -> dict[str, object]:
    value = payload.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _routine_error(
            f"routine.registry.{key}_type",
            f"Routine field '{key}' must be an object when present",
            path=("routines", routine_id, key),
            details={"path": str(registry_path), "id": routine_id, "actual_type": type(value).__name__},
        )
    return dict(value)


def _require_non_empty_string(payload: dict[str, object], key: str, *, registry_path: Path, path: tuple[str, ...]) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise _routine_error(
            f"routine.registry.{key}",
            f"Routine field '{key}' must be a non-empty string",
            path=path,
            details={"path": str(registry_path), "actual_type": type(value).__name__},
        )
    return value


def _require_non_empty_string_array(value: object, *, routine_id: str, registry_path: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise _routine_error(
            "routine.registry.failure_modes_type",
            "Routine field 'failure_modes' must be a non-empty array",
            path=("routines", routine_id, "failure_modes"),
            details={"path": str(registry_path), "id": routine_id, "actual_type": type(value).__name__},
        )
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise _routine_error(
                "routine.registry.failure_mode_type",
                "Routine failure modes must be non-empty strings",
                path=("routines", routine_id, "failure_modes", str(index)),
                details={"path": str(registry_path), "id": routine_id, "actual_type": type(item).__name__},
            )
        normalized.append(item)
    return tuple(normalized)


def _validate_unknown_fields(payload: dict[str, object], allowed_fields: frozenset[str], *, source: str, path: tuple[str, ...]) -> None:
    extras = sorted(key for key in payload if key not in allowed_fields)
    if not extras:
        return
    raise _routine_error(
        "routine.registry.unknown_field",
        f"Unknown field '{extras[0]}' in routine registry",
        path=path + (extras[0],),
        details={"source": source, "unknown_field": extras[0], "allowed_fields": sorted(allowed_fields)},
    )


def _detect_duplicate_routine_ids(text: str, *, source: str) -> None:
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return
    if not isinstance(root, yaml.MappingNode):
        return
    routines_node = None
    for key_node, value_node in root.value:
        if getattr(key_node, "value", None) == "routines":
            routines_node = value_node
            break
    if not isinstance(routines_node, yaml.MappingNode):
        return
    seen: set[str] = set()
    for key_node, _ in routines_node.value:
        routine_id = getattr(key_node, "value", None)
        if not isinstance(routine_id, str):
            continue
        if routine_id in seen:
            raise _routine_error(
                "routine.registry.duplicate_id",
                f"Routine '{routine_id}' is declared more than once",
                path=("routines", routine_id),
                details={"source": source, "id": routine_id},
            )
        seen.add(routine_id)


def _routine_error(code: str, message: str, *, path: tuple[str, ...] = (), details: dict[str, object] | None = None) -> RoutineRegistryError:
    payload = {"category": "routine_registry", **(details or {})}
    return RoutineRegistryError((Diagnostic(code=code, level="error", message=message, path=path, details=payload),))
