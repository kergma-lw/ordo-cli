"""Runtime resolution for value-bearing local-expression surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONArray, JSONObject, JSONValue, authored_string_style
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow

from .local_expression_engine.core import ReadOnlyObservationSession
from .local_expressions import resolve_embedded_value_local_expression, resolve_value_local_expression


@dataclass(frozen=True, slots=True)
class ValueResolutionError(Exception):
    """Structured runtime value resolution error."""

    code: str
    message: str
    details: JSONObject = field(default_factory=dict)
    _state_missing_target: tuple[str, str, tuple[str, ...]] | None = field(default=None, repr=False, compare=False)

    def to_diagnostic(self, *, path: tuple[str, ...] = ()) -> Diagnostic:
        return Diagnostic(
            code=self.code,
            level="error",
            message=self.message,
            path=path,
            details=dict(self.details),
            _state_missing_target=self._state_missing_target,
        )

    def to_diagnostics(self, *, path: tuple[str, ...] = ()) -> tuple[Diagnostic, ...]:
        diagnostics = [self.to_diagnostic(path=path)]
        nested = self.details.get("probe_diagnostics")
        if isinstance(nested, list):
            for item in nested:
                diagnostic = _diagnostic_from_contract(item)
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
        return tuple(diagnostics)


def resolve_runtime_value(
    value: JSONValue,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONObject] | None = None,
    allow_boolean_composition: bool = False,
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    """Resolve value-bearing local-expression surfaces against workflow inputs, state, and step results."""

    resolved_step_results = dict(workflow.step_results) if step_results is None else step_results
    if _is_format_object(value):
        return _resolve_format_object(value, workflow, step_results=resolved_step_results, observation_session=observation_session)
    if isinstance(value, list):
        return [
            resolve_runtime_value(
                item,
                workflow,
                step_results=resolved_step_results,
                observation_session=observation_session,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: resolve_runtime_value(
                item,
                workflow,
                step_results=resolved_step_results,
                observation_session=observation_session,
            )
            for key, item in value.items()
        }
    if not isinstance(value, str):
        return value

    authored_style = authored_string_style(value)
    if authored_style in {"single", "double", "other"} and _extract_expression(value) is None:
        return str(value)

    if authored_style is None and _extract_expression(value) is None:
        return value

    resolver = resolve_value_local_expression if authored_style == "plain" else resolve_embedded_value_local_expression
    return resolver(
        value,
        workflow,
        step_results=resolved_step_results,
        allow_boolean_composition=allow_boolean_composition,
        observation_session=observation_session,
    )


def _extract_expression(value: str) -> str | None:
    if value.startswith("${") and value.endswith("}") and len(value) >= 4:
        return value[2:-1]
    return None


def _diagnostic_from_contract(value: JSONValue) -> Diagnostic | None:
    if not isinstance(value, dict):
        return None
    code = value.get("code")
    level = value.get("level")
    message = value.get("message")
    raw_path = value.get("path", [])
    details = value.get("details", {})
    if not isinstance(code, str) or not isinstance(level, str) or not isinstance(message, str):
        return None
    if not isinstance(raw_path, list) or not all(isinstance(item, str) for item in raw_path):
        return None
    if not isinstance(details, dict):
        return None
    return Diagnostic(code=code, level=level, message=message, path=tuple(raw_path), details=details)


def _is_format_object(value: JSONValue) -> bool:
    return isinstance(value, dict) and "format" in value and set(value.keys()) <= {"format", "args"}


def _resolve_format_object(
    value: JSONObject,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONObject],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    template = value.get("format")
    if not isinstance(template, str):
        return value
    args_value = value.get("args", [])
    if not isinstance(args_value, list):
        return value
    resolved_args = [
        resolve_runtime_value(
            item,
            workflow,
            step_results=step_results,
            observation_session=observation_session,
        )
        for item in args_value
    ]
    placeholder_count = template.count("{}")
    if placeholder_count != len(resolved_args):
        raise ValueResolutionError(
            code="runtime.value.format_args_invalid",
            message="Built-in value expression 'format' received the wrong number of arguments",
            details={"placeholders": placeholder_count, "arguments": len(resolved_args)},
        )
    return template.format(*tuple(_coerce_format_scalar(argument) for argument in resolved_args))


def _coerce_format_scalar(value: JSONValue) -> JSONValue:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueResolutionError(
        code="runtime.value.format_arg_type_invalid",
        message="Built-in value expression 'format' requires scalar arguments",
        details={"actual_type": type(value).__name__},
    )
