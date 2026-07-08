"""Helpers for runtime-scoped reusable fragment runs."""

from __future__ import annotations

from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONValue
from ordo.model.workflow import RunBlock, Workflow

from .loading import LoadError, _load_included_fragment_payload, _load_workflow_blocks
from .value_resolution import ValueResolutionError, resolve_runtime_value


def materialize_run_workflow(run_block: RunBlock, caller_workflow: Workflow, *, block_index: int) -> Workflow | Diagnostic:
    """Load and bind one reusable fragment run into an executable sub-workflow."""

    if run_block.resolved_path is None:
        return Diagnostic(
            code="runtime.run.unresolved_path",
            level="error",
            message="Run block could not resolve its fragment path",
            path=("blocks", str(block_index), "run"),
            details={"reference": run_block.run},
        )

    try:
        include_bindings = _evaluate_run_bindings(run_block.with_, caller_workflow, block_index=block_index)
    except ValueResolutionError as exc:
        return exc.to_diagnostic(path=("blocks", str(block_index), "with"))

    run_path = Path(run_block.resolved_path)
    launch_dir = Path(caller_workflow.launch_dir) if caller_workflow.launch_dir is not None else run_path.parent
    try:
        payload = _load_included_fragment_payload(
            run_path,
            launch_dir=launch_dir,
            stack=(),
            depth=0,
            include_bindings=include_bindings,
            include_node_path=("blocks", str(block_index), "run"),
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
            path=("blocks", str(block_index), "run"),
            details={"reference": run_block.run, "actual_type": type(payload).__name__},
        )

    try:
        blocks = _load_workflow_blocks({"blocks": blocks_payload}, source=str(run_path))
    except LoadError as exc:
        return exc.diagnostics[0]

    return Workflow(
        version=caller_workflow.version,
        workflow=f"{caller_workflow.workflow}::{run_block.run}",
        inputs=caller_workflow.inputs,
        declared_inputs=caller_workflow.declared_inputs,
        state_needs=caller_workflow.state_needs,
        state_bindings=caller_workflow.state_bindings,
        states=caller_workflow.states,
        blocks=blocks,
        source_path=str(run_path),
        launch_dir=str(launch_dir),
    )


def evaluate_run_condition(run_block: RunBlock, caller_workflow: Workflow, *, block_index: int) -> bool | Diagnostic:
    if run_block.if_ is None:
        return True
    try:
        value = resolve_runtime_value(run_block.if_, caller_workflow, allow_boolean_composition=True)
    except ValueResolutionError as exc:
        return exc.to_diagnostic(path=("blocks", str(block_index), "if"))
    if isinstance(value, bool):
        return value
    return Diagnostic(
        code="runtime.run.if.result_type",
        level="error",
        message="Run condition must evaluate to a boolean value",
        path=("blocks", str(block_index), "if"),
        details={"actual_type": type(value).__name__},
    )


def _evaluate_run_bindings(bindings: JSONObject, workflow: Workflow, *, block_index: int) -> JSONObject:
    resolved: JSONObject = {}
    for key, value in bindings.items():
        resolved[key] = _resolve_run_binding_value(value, workflow, block_index=block_index, key=key)
    return resolved


def _resolve_run_binding_value(value: JSONValue, workflow: Workflow, *, block_index: int, key: str) -> JSONValue:
    try:
        return resolve_runtime_value(value, workflow, allow_boolean_composition=True)
    except ValueResolutionError as exc:
        raise ValueResolutionError(
            code=exc.code,
            message=exc.message,
            details={**dict(exc.details), "run_block_index": block_index, "binding": key},
        ) from exc
