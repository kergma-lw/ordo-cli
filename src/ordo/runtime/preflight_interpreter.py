"""Read-only helpers for preflight step interpretation."""

from __future__ import annotations

from ordo.model.json import JSONObject, JSONValue
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Step, Workflow

from .providers import GuardProbe
from .resolution import ResolvedOperation
from .value_resolution import ValueResolutionError, resolve_runtime_value


def resolve_preflight_value(
    value: JSONValue,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONObject] | None = None,
) -> JSONValue:
    """Resolve one preflight value against current workflow and stored step results."""

    return resolve_runtime_value(value, workflow, step_results=step_results)


def evaluate_preflight_step_condition(
    step: Step,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONObject] | None = None,
) -> bool | ValueResolutionError | None:
    """Evaluate one step `if` condition from currently available preflight knowledge."""

    if step.if_ is None:
        return True
    try:
        value = resolve_runtime_value(step.if_, workflow, step_results=step_results, allow_boolean_composition=True)
    except ValueResolutionError as exc:
        return exc
    if isinstance(value, bool):
        return value
    return None


def evaluate_preflight_value_step(
    step: Step,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONObject] | None = None,
) -> OperationResult:
    """Evaluate one pure value step without executing any effectful behavior."""

    if step.value is None:
        return OperationResult(status="state_error", summary=f"Step '{step.name}' is not a value step")
    try:
        value = resolve_preflight_value(step.value, workflow, step_results=step_results)
    except ValueResolutionError as exc:
        return OperationResult(status="state_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))
    return OperationResult(
        status="ok",
        summary=f"Materialized derived value for step '{step.name}'",
        outputs={"value": value},
    )


def store_preflight_register_output(
    register_name: str,
    result: OperationResult,
    *,
    step_results: dict[str, OperationResult | JSONObject],
) -> None:
    """Store one read-only step result for later preflight dataflow."""

    step_results[register_name] = {
        "status": result.status,
        "summary": result.summary,
        "outputs": dict(result.outputs),
    }


def evaluate_preflight_probe_step(
    step: Step,
    resolved_step: ResolvedOperation,
    workflow: Workflow,
    *,
    guard_probe: GuardProbe,
) -> OperationResult:
    """Evaluate one read-only probe step through the runtime guard probe surface."""

    if resolved_step.operation.kind != "probe":
        return OperationResult(status="state_error", summary=f"Step '{step.name}' is not a read-only probe")
    return guard_probe(resolved_step, workflow)
