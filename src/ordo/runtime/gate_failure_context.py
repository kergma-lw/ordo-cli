"""Evaluation helpers for gate failure diagnostics."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Step, Workflow

from .local_expression_engine.core import ReadOnlyObservationSession
from .value_resolution import ValueResolutionError, resolve_runtime_value


def evaluate_gate_failure_context(
    step: Step,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONObject] | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
) -> tuple[JSONObject, JSONObject]:
    """Resolve authored `gate.on_fail` expressions without changing gate verdict."""

    if not isinstance(step.gate_on_fail, dict) or not step.gate_on_fail:
        return {}, {}
    context: JSONObject = {}
    errors: JSONObject = {}
    for key, value in step.gate_on_fail.items():
        if not isinstance(key, str):
            continue
        try:
            context[key] = resolve_runtime_value(
                value,
                workflow,
                step_results=step_results,
                allow_boolean_composition=True,
                observation_session=observation_session,
            )
        except ValueResolutionError as exc:
            errors[key] = {
                "code": exc.code,
                "message": exc.message,
                **({"details": dict(exc.details)} if exc.details else {}),
            }
    return context, errors
