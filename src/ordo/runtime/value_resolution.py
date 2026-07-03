"""Runtime value resolution for workflow inputs and state reads."""

from __future__ import annotations

from dataclasses import dataclass, field

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONArray, JSONObject, JSONValue
from ordo.model.workflow import Workflow

from .state import RuntimeStateError, RuntimeStateRegistry, read_state_document, read_state_value
from .state_paths import StatePathParseError, parse_state_path


@dataclass(frozen=True, slots=True)
class ValueResolutionError(Exception):
    """Structured runtime value resolution error."""

    code: str
    message: str
    details: JSONObject = field(default_factory=dict)

    def to_diagnostic(self, *, path: tuple[str, ...] = ()) -> Diagnostic:
        return Diagnostic(
            code=self.code,
            level="error",
            message=self.message,
            path=path,
            details=dict(self.details),
        )


def resolve_runtime_value(value: JSONValue, workflow: Workflow) -> JSONValue:
    """Resolve runtime value references against workflow inputs and runtime state."""

    if isinstance(value, list):
        return [resolve_runtime_value(item, workflow) for item in value]
    if isinstance(value, dict):
        return {key: resolve_runtime_value(item, workflow) for key, item in value.items()}
    if not isinstance(value, str):
        return value

    expression = _extract_expression(value)
    if expression is None:
        return value
    if expression.startswith("inputs."):
        return _resolve_input_reference(tuple(expression.split(".")), workflow)
    if expression.startswith("states."):
        return _resolve_state_reference(expression, workflow)
    return value


def _extract_expression(value: str) -> str | None:
    if value.startswith("${") and value.endswith("}") and len(value) >= 4:
        return value[2:-1]
    return None


def _resolve_input_reference(parts: tuple[str, ...], workflow: Workflow) -> JSONValue:
    current: JSONValue = workflow.inputs
    for part in parts[1:]:
        if not isinstance(current, dict) or part not in current:
            raise ValueResolutionError(
                code="runtime.value.input_missing",
                message=f"Workflow input reference '{'.'.join(parts)}' is missing",
                details={"reference": ".".join(parts)},
            )
        current = current[part]
    return current


def _resolve_state_reference(expression: str, workflow: Workflow) -> JSONValue:
    try:
        parsed = parse_state_path(expression)
    except StatePathParseError as exc:
        raise ValueResolutionError(
            code="runtime.value.state_path_invalid",
            message=exc.message,
            details={
                "expression": expression,
                "position": exc.position,
                "end": exc.end if exc.end is not None else exc.position,
            },
        ) from exc

    registry = RuntimeStateRegistry.from_workflow(workflow)
    location = registry.require(parsed.state_name)
    document = read_state_document(location)
    key_value = _resolve_input_reference(parsed.key_reference, workflow)
    if isinstance(key_value, dict) or isinstance(key_value, list):
        raise ValueResolutionError(
            code="runtime.value.state_key_invalid",
            message="Runtime state key reference must resolve to a scalar value",
            details={"expression": expression, "reference": ".".join(parsed.key_reference)},
        )

    try:
        value = read_state_value(document, key=str(key_value), fields=parsed.fields)
    except RuntimeStateError as exc:
        raise ValueResolutionError(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ) from exc
    if value is None:
        raise ValueResolutionError(
            code="runtime.value.state_missing",
            message="Runtime state value is missing",
            details={"expression": expression, "state": parsed.state_name, "key": str(key_value), "fields": list(parsed.fields)},
        )
    return value
