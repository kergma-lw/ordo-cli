"""Helpers for runtime-scoped reusable fragment runs."""

from __future__ import annotations

from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONValue
from ordo.model.workflow import Step, Workflow

from .loading import LoadError, _load_included_fragment_payload, _load_workflow_blocks
from .value_resolution import ValueResolutionError, resolve_runtime_value


def materialize_run_workflow(step: Step, caller_workflow: Workflow, *, block_index: int, step_index: int) -> Workflow | Diagnostic:
    """Load and bind one reusable fragment run into an executable sub-workflow."""

    if step.resolved_run_path is None:
        return Diagnostic(
            code="runtime.run.unresolved_path",
            level="error",
            message="Run block could not resolve its fragment path",
            path=("blocks", str(block_index), "steps", str(step_index), "run"),
            details={"reference": step.run},
        )

    try:
        include_bindings = _evaluate_run_bindings(step.run_with, caller_workflow, block_index=block_index, step_index=step_index)
    except ValueResolutionError as exc:
        return exc.to_diagnostic(path=("blocks", str(block_index), "steps", str(step_index), "with"))

    run_path = Path(step.resolved_run_path)
    launch_dir = Path(caller_workflow.launch_dir) if caller_workflow.launch_dir is not None else run_path.parent
    try:
        payload = _load_included_fragment_payload(
            run_path,
            launch_dir=launch_dir,
            stack=(),
            depth=0,
            include_bindings=include_bindings,
            include_node_path=("blocks", str(block_index), "steps", str(step_index), "run"),
        )
    except LoadError as exc:
        return exc.diagnostics[0]

    if isinstance(payload, list):
        blocks_payload = payload
    elif isinstance(payload, dict) and "blocks" in payload:
        blocks_payload = payload.get("blocks")
    elif isinstance(payload, dict) and ({"steps", "guards", "run"} & set(payload.keys())):
        blocks_payload = [payload]
    else:
        blocks_payload = None
    if not isinstance(blocks_payload, list):
        return Diagnostic(
            code="runtime.run.fragment_shape",
            level="error",
            message="Run fragment must normalize to workflow block content",
            path=("blocks", str(block_index), "steps", str(step_index), "run"),
            details={"reference": step.run, "actual_type": type(payload).__name__},
        )

    try:
        blocks = _load_workflow_blocks({"blocks": blocks_payload}, source=str(run_path))
    except LoadError as exc:
        return exc.diagnostics[0]

    return Workflow(
        version=caller_workflow.version,
        workflow=f"{caller_workflow.workflow}::{step.run}",
        inputs=caller_workflow.inputs,
        declared_inputs=caller_workflow.declared_inputs,
        state_needs=caller_workflow.state_needs,
        state_bindings=caller_workflow.state_bindings,
        states=caller_workflow.states,
        blocks=blocks,
        source_path=str(run_path),
        launch_dir=str(launch_dir),
    )


def evaluate_run_condition(step: Step, caller_workflow: Workflow, *, block_index: int, step_index: int) -> bool | Diagnostic:
    if step.if_ is None:
        return True
    try:
        value = resolve_runtime_value(step.if_, caller_workflow, allow_boolean_composition=True)
    except ValueResolutionError as exc:
        return exc.to_diagnostic(path=("blocks", str(block_index), "steps", str(step_index), "if"))
    if isinstance(value, bool):
        return value
    return Diagnostic(
        code="runtime.run.if.result_type",
        level="error",
        message="Run condition must evaluate to a boolean value",
        path=("blocks", str(block_index), "steps", str(step_index), "if"),
        details={"actual_type": type(value).__name__},
    )


def _evaluate_run_bindings(bindings: JSONObject, workflow: Workflow, *, block_index: int, step_index: int) -> JSONObject:
    resolved: JSONObject = {}
    for key, value in bindings.items():
        resolved[key] = _resolve_run_binding_value(value, workflow, block_index=block_index, step_index=step_index, key=key)
    return resolved


def _resolve_run_binding_value(value: JSONValue, workflow: Workflow, *, block_index: int, step_index: int, key: str) -> JSONValue:
    try:
        return resolve_runtime_value(value, workflow, allow_boolean_composition=True)
    except ValueResolutionError as exc:
        raise ValueResolutionError(
            code=exc.code,
            message=exc.message,
            details={**dict(exc.details), "run_block_index": block_index, "run_step_index": step_index, "binding": key},
        ) from exc
