"""Runtime value resolution for workflow inputs and state reads."""

from __future__ import annotations

from dataclasses import dataclass, field

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONArray, JSONObject, JSONValue
from ordo.model.workflow import Workflow

from .state import RuntimeStateError, resolve_state_target, resolve_workflow_input_reference, read_state_document, read_state_value


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
    try:
        return resolve_workflow_input_reference(parts, workflow)
    except RuntimeStateError as exc:
        raise ValueResolutionError(
            code="runtime.value.input_missing",
            message=exc.message,
            details=exc.details,
        ) from exc


def _resolve_state_reference(expression: str, workflow: Workflow) -> JSONValue:
    try:
        target = resolve_state_target(expression, workflow)
    except RuntimeStateError as exc:
        raise ValueResolutionError(
            code=(
                "runtime.value.state_path_invalid"
                if exc.code == "runtime.state.path_invalid"
                else "runtime.value.state_key_invalid"
                if exc.code == "runtime.state.key_invalid"
                else "runtime.value.input_missing"
                if exc.code == "runtime.state.input_missing"
                else exc.code
            ),
            message=exc.message,
            details=exc.details,
        )
    try:
        document = read_state_document(target.location)
        value = read_state_value(document, key=target.key, fields=target.fields)
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
            details={"expression": expression, "state": target.location.name, "key": target.key, "fields": list(target.fields)},
        )
    return value
