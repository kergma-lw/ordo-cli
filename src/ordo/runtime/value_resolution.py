"""Runtime resolution for embedded-value local-expression surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONArray, JSONObject, JSONValue
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow

from .local_expressions import resolve_embedded_value_local_expression


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


def resolve_runtime_value(
    value: JSONValue,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONObject] | None = None,
    allow_boolean_composition: bool = False,
) -> JSONValue:
    """Resolve embedded-value local-expression surfaces against workflow inputs, state, and step results."""

    resolved_step_results = dict(workflow.step_results) if step_results is None else step_results
    if _is_format_object(value):
        return _resolve_format_object(value, workflow, step_results=resolved_step_results)
    if isinstance(value, list):
        return [resolve_runtime_value(item, workflow, step_results=resolved_step_results) for item in value]
    if isinstance(value, dict):
        return {key: resolve_runtime_value(item, workflow, step_results=resolved_step_results) for key, item in value.items()}
    if not isinstance(value, str):
        return value

    if _extract_expression(value) is None:
        return value
    try:
        return resolve_embedded_value_local_expression(
            value,
            workflow,
            step_results=resolved_step_results,
            allow_boolean_composition=allow_boolean_composition,
        )
    except ValueResolutionError:
        raise


def _extract_expression(value: str) -> str | None:
    if value.startswith("${") and value.endswith("}") and len(value) >= 4:
        return value[2:-1]
    return None


def _is_format_object(value: JSONValue) -> bool:
    return isinstance(value, dict) and "format" in value and set(value.keys()) <= {"format", "args"}


def _resolve_format_object(value: JSONObject, workflow: Workflow, *, step_results: dict[str, OperationResult | JSONObject]) -> JSONValue:
    template = value.get("format")
    if not isinstance(template, str):
        return value
    args_value = value.get("args", [])
    if not isinstance(args_value, list):
        return value
    resolved_args = [resolve_runtime_value(item, workflow, step_results=step_results) for item in args_value]
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
