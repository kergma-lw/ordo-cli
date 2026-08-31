"""Helpers for runtime-scoped reusable fragment runs."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONValue
from ordo.model.workflow import GuardBlock, Step, StepBlock, Workflow

from .local_expression_contexts import LocalExpressionContext
from .local_expressions import resolve_condition_value
from .loading import LoadError, _load_included_fragment_payload, _load_workflow_blocks, load_workflow_payload
from .value_resolution import ValueResolutionError, resolve_runtime_value


@dataclass(frozen=True, slots=True)
class CheckRunExpansionDecision:
    admissible: bool
    reason: str
    workflow: Workflow | None = None
    item_index: int | None = None
    item_value: JSONValue | None = None


def materialize_run_workflow(
    step: Step,
    caller_workflow: Workflow,
    *,
    block_index: int,
    step_index: int,
    extra_bindings: JSONObject | None = None,
) -> Workflow | Diagnostic:
    """Load and bind one reusable fragment run into an executable sub-workflow."""

    if step.steps is not None:
        return _materialize_inline_run_workflow(
            step,
            caller_workflow,
            block_index=block_index,
            step_index=step_index,
            extra_bindings=extra_bindings,
        )

    if step.resolved_run_path is None:
        return Diagnostic(
            code="runtime.run.unresolved_path",
            level="error",
            message="Run block could not resolve its fragment path",
            path=("blocks", str(block_index), "steps", str(step_index), "run"),
            details={"reference": step.run},
        )

    binding_workflow = caller_workflow
    if extra_bindings and "item" in extra_bindings:
        binding_workflow = Workflow(
            version=caller_workflow.version,
            workflow=caller_workflow.workflow,
            profile=caller_workflow.profile,
            inputs={**caller_workflow.inputs, "__iteration_item__": extra_bindings["item"]},
            declared_inputs=caller_workflow.declared_inputs,
            explicit_input_keys=caller_workflow.explicit_input_keys,
            protected_input_keys=caller_workflow.protected_input_keys,
            let_bindings=caller_workflow.let_bindings,
            state_needs=caller_workflow.state_needs,
            state_bindings=caller_workflow.state_bindings,
            states=caller_workflow.states,
            step_results=caller_workflow.step_results,
            connector_contexts=caller_workflow.connector_contexts,
            blocks=caller_workflow.blocks,
            source_path=caller_workflow.source_path,
            launch_dir=caller_workflow.launch_dir,
            launch_profile_name=caller_workflow.launch_profile_name,
            launch_profile_source=caller_workflow.launch_profile_source,
            playbook_owned_pre_run=caller_workflow.playbook_owned_pre_run,
        )
    try:
        include_bindings = _evaluate_run_bindings(step.run_with, binding_workflow, block_index=block_index, step_index=step_index)
    except ValueResolutionError as exc:
        return exc.to_diagnostic(path=("blocks", str(block_index), "steps", str(step_index), "with"))
    if extra_bindings:
        include_bindings = {**include_bindings, **extra_bindings}

    run_path = Path(step.resolved_run_path)
    launch_dir = Path(caller_workflow.launch_dir) if caller_workflow.launch_dir is not None else run_path.parent
    payload = load_run_target_payload(
        run_path=run_path,
        launch_dir=launch_dir,
        bindings=include_bindings,
        node_path=("blocks", str(block_index), "steps", str(step_index), "run"),
    )
    if isinstance(payload, Diagnostic):
        return payload
    return build_run_target_workflow(
        payload,
        caller_workflow=caller_workflow,
        step=step,
        run_path=run_path,
        launch_dir=launch_dir,
        node_path=("blocks", str(block_index), "steps", str(step_index), "run"),
        bindings=include_bindings,
    )


def _materialize_inline_run_workflow(
    step: Step,
    caller_workflow: Workflow,
    *,
    block_index: int,
    step_index: int,
    extra_bindings: JSONObject | None,
) -> Workflow:
    item_value = None if extra_bindings is None else extra_bindings.get("item")
    materialized_inputs = dict(caller_workflow.inputs)
    if extra_bindings and "item" in extra_bindings:
        materialized_inputs["__iteration_item__"] = item_value
    if step.run_with:
        materialized_inputs["__fragment_args__"] = _evaluate_run_bindings(step.run_with, caller_workflow, block_index=block_index, step_index=step_index)
    if step.run_inputs:
        materialized_inputs.update(step.run_inputs)
    return Workflow(
        version=caller_workflow.version,
        workflow=f"{caller_workflow.workflow}::{step.name}",
        inputs=materialized_inputs,
        declared_inputs=caller_workflow.declared_inputs,
        explicit_input_keys=caller_workflow.explicit_input_keys,
        protected_input_keys=caller_workflow.protected_input_keys,
        let_bindings={},
        state_needs=caller_workflow.state_needs,
        state_bindings=caller_workflow.state_bindings,
        states=caller_workflow.states,
        step_results={},
        connector_contexts=caller_workflow.connector_contexts,
        blocks=(StepBlock(steps=tuple(step.steps or ())),),
        source_path=caller_workflow.source_path,
        launch_dir=caller_workflow.launch_dir,
        launch_profile_name=caller_workflow.launch_profile_name,
        launch_profile_source=caller_workflow.launch_profile_source,
        playbook_owned_pre_run=caller_workflow.playbook_owned_pre_run,
    )


def classify_run_for_check(
    step: Step,
    caller_workflow: Workflow,
    *,
    block_index: int,
    step_index: int,
    extra_bindings: JSONObject | None = None,
    item_index: int | None = None,
    item_value: JSONValue | None = None,
) -> CheckRunExpansionDecision:
    if step.run is None and step.steps is None:
        return CheckRunExpansionDecision(admissible=False, reason="run_target_unknown")
    if step.run is not None and step.resolved_run_path is None and step.steps is None:
        return CheckRunExpansionDecision(admissible=False, reason="run_target_unknown")
    try:
        binding_workflow = caller_workflow
        if extra_bindings and "item" in extra_bindings:
            binding_workflow = Workflow(
                version=caller_workflow.version,
                workflow=caller_workflow.workflow,
                profile=caller_workflow.profile,
                inputs={**caller_workflow.inputs, "__iteration_item__": extra_bindings["item"]},
                declared_inputs=caller_workflow.declared_inputs,
                explicit_input_keys=caller_workflow.explicit_input_keys,
                protected_input_keys=caller_workflow.protected_input_keys,
                let_bindings=caller_workflow.let_bindings,
                state_needs=caller_workflow.state_needs,
                state_bindings=caller_workflow.state_bindings,
                states=caller_workflow.states,
                step_results=caller_workflow.step_results,
                connector_contexts=caller_workflow.connector_contexts,
                blocks=caller_workflow.blocks,
                source_path=caller_workflow.source_path,
                launch_dir=caller_workflow.launch_dir,
                launch_profile_name=caller_workflow.launch_profile_name,
                launch_profile_source=caller_workflow.launch_profile_source,
                playbook_owned_pre_run=caller_workflow.playbook_owned_pre_run,
            )
        _evaluate_run_bindings(step.run_with, binding_workflow, block_index=block_index, step_index=step_index)
    except ValueResolutionError:
        return CheckRunExpansionDecision(admissible=False, reason="run_args_not_known")
    materialized = materialize_run_workflow(step, caller_workflow, block_index=block_index, step_index=step_index, extra_bindings=extra_bindings)
    if isinstance(materialized, Diagnostic):
        reason = "run_target_not_loadable"
        if materialized.code == "runtime.run.unresolved_path":
            reason = "run_target_unknown"
        return CheckRunExpansionDecision(admissible=False, reason=reason)
    analyzable_reason = _check_analyzable_run_workflow(materialized)
    if analyzable_reason is not None:
        return CheckRunExpansionDecision(admissible=False, reason=analyzable_reason, workflow=materialized, item_index=item_index, item_value=item_value)
    return CheckRunExpansionDecision(admissible=True, reason="run_expandable", workflow=materialized, item_index=item_index, item_value=item_value)


def evaluate_run_condition(step: Step, caller_workflow: Workflow, *, block_index: int, step_index: int) -> bool | Diagnostic:
    if step.if_ is None:
        return True
    try:
        value = resolve_condition_value(step.if_, caller_workflow, context=LocalExpressionContext.STEP_CONDITION)
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


def _check_analyzable_run_workflow(workflow: Workflow) -> str | None:
    for block in workflow.blocks:
        if isinstance(block, GuardBlock):
            continue
        assert isinstance(block, StepBlock)
        for step in block.steps:
            if (
                step.operation is None
                and step.run is None
                and step.steps is None
                and step.profile_switch is None
                and step.value is None
                and step.result is None
                and step.publish is None
                and step.state_set is None
                and step.state_delete is None
                and step.gate is not None
            ):
                continue
            if step.profile_switch is not None:
                continue
            if step.run is not None or step.steps is not None:
                continue
            if (
                step.operation is not None
                or step.value is not None
                or step.state_set is not None
                or step.state_delete is not None
                or step.result is not None
                or step.publish is not None
            ):
                continue
            return "run_subtree_not_check_analyzable"
    return None


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


def load_run_target_payload(
    *,
    run_path: Path,
    launch_dir: Path,
    bindings: JSONObject,
    node_path: tuple[str, ...],
) -> JSONValue | Diagnostic:
    try:
        return _load_included_fragment_payload(
            run_path,
            launch_dir=launch_dir,
            stack=(),
            depth=0,
            include_bindings=bindings,
            include_node_path=node_path,
            scope_mode="run",
        )
    except LoadError as exc:
        return exc.diagnostics[0]


def build_run_target_workflow(
    payload: JSONValue,
    *,
    caller_workflow: Workflow,
    step: Step,
    run_path: Path,
    launch_dir: Path,
    node_path: tuple[str, ...],
    bindings: JSONObject | None = None,
) -> Workflow | Diagnostic:
    effective_bindings = {} if bindings is None else dict(bindings)
    if isinstance(payload, dict) and "version" in payload and "workflow" in payload:
        try:
            nested_workflow = load_workflow_payload(payload, source=str(run_path), launch_dir=launch_dir)
        except LoadError as exc:
            return exc.diagnostics[0]
        return Workflow(
            version=nested_workflow.version,
            workflow=f"{caller_workflow.workflow}::{nested_workflow.workflow}",
            profile=nested_workflow.profile,
            inputs={**nested_workflow.inputs, **caller_workflow.inputs, **step.run_inputs, **effective_bindings, "__fragment_args__": effective_bindings},
            declared_inputs={**caller_workflow.declared_inputs, **nested_workflow.declared_inputs},
            explicit_input_keys=_merge_explicit_input_keys(caller_workflow, nested_workflow),
            protected_input_keys=caller_workflow.protected_input_keys,
            let_bindings=nested_workflow.let_bindings,
            state_needs={**caller_workflow.state_needs, **nested_workflow.state_needs},
            state_bindings={**caller_workflow.state_bindings, **nested_workflow.state_bindings, **dict(step.run_state_bindings)},
            states={**caller_workflow.states, **nested_workflow.states, **dict(step.run_states)},
            step_results={},
            connector_contexts=caller_workflow.connector_contexts,
            blocks=nested_workflow.blocks,
            source_path=nested_workflow.source_path,
            launch_dir=nested_workflow.launch_dir,
            launch_profile_name=caller_workflow.launch_profile_name,
            launch_profile_source=caller_workflow.launch_profile_source,
            playbook_owned_pre_run=caller_workflow.playbook_owned_pre_run or step.run_origin == "playbook_pre_run",
        )

    blocks_payload: JSONValue | None
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
            path=node_path,
            details={"reference": step.run, "actual_type": type(payload).__name__},
        )

    try:
        blocks = _load_workflow_blocks({"blocks": blocks_payload}, source=str(run_path))
    except LoadError as exc:
        return exc.diagnostics[0]

    return Workflow(
        version=caller_workflow.version,
        workflow=f"{caller_workflow.workflow}::{step.run}",
        inputs={**caller_workflow.inputs, **step.run_inputs, **effective_bindings, "__fragment_args__": effective_bindings},
        declared_inputs=caller_workflow.declared_inputs,
        explicit_input_keys=caller_workflow.explicit_input_keys,
        protected_input_keys=caller_workflow.protected_input_keys,
        let_bindings={},
        state_needs=caller_workflow.state_needs,
        state_bindings=step.run_state_bindings or caller_workflow.state_bindings,
        states=step.run_states or caller_workflow.states,
        step_results={},
        connector_contexts=caller_workflow.connector_contexts,
        blocks=blocks,
        source_path=str(run_path),
        launch_dir=str(launch_dir),
        launch_profile_name=caller_workflow.launch_profile_name,
        launch_profile_source=caller_workflow.launch_profile_source,
        playbook_owned_pre_run=caller_workflow.playbook_owned_pre_run or step.run_origin == "playbook_pre_run",
    )


def _merge_explicit_input_keys(*workflows: Workflow) -> tuple[str, ...]:
    merged: list[str] = []
    for workflow in workflows:
        for key in workflow.explicit_input_keys:
            if key not in merged:
                merged.append(key)
    return tuple(merged)
