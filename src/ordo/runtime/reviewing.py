"""Review mode for authoring-oriented findings over the shared analysis tree."""

from __future__ import annotations

from pathlib import Path

from ordo.model.json import authored_string_style
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, RuntimeResult, RuntimeStatus
from ordo.model.workflow import GuardBlock, RunBlock, Step, StepBlock, Workflow

from .checking import check_workflow
from .local_expression_contexts import LocalExpressionContext
from .local_expression_engine.core import (
    AdapterBindingNode,
    AdapterInvocationNode,
    BinaryNode,
    BuiltinCallNode,
    CallArgumentNode,
    CallNode,
    FilterApplicationNode,
    ListNode,
    ObjectEntryNode,
    ObjectNode,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode,
    StepReferenceNode,
    UnaryNode,
    ValueExpressionNode,
    render_expression_text,
)
from .local_expressions import LocalExpressionParseError, extract_embedded_local_expression, parse_condition_local_expression, parse_value_local_expression
from .providers import ConnectorProvider, GuardProbe, get_default_connector_provider
from .value_resolution import ValueResolutionError, resolve_runtime_value


def review_workflow(
    workflow: Workflow,
    *,
    profile: Profile | None = None,
    available_profiles: dict[str, Profile] | None = None,
    profile_working_directories: dict[str, Path | None] | None = None,
    guard_probe: GuardProbe | None = None,
    connector_provider: ConnectorProvider | None = None,
) -> RuntimeResult:
    """Return authoring findings without changing runtime executability semantics."""

    check_result = check_workflow(
        workflow,
        profile=profile,
        available_profiles=available_profiles,
        profile_working_directories=profile_working_directories,
        guard_probe=guard_probe,
        connector_provider=connector_provider,
    )
    if check_result.status in {RuntimeStatus.VALIDATION_ERROR, RuntimeStatus.RESOLUTION_ERROR}:
        validation_findings = _find_diagnostic_review_hints(check_result)
        return RuntimeResult(
            mode=Mode.REVIEW,
            status=check_result.status,
            diagnostics=check_result.diagnostics,
            plan=check_result.plan,
            outputs={
                **dict(check_result.outputs),
                "review_status": "unavailable",
                "finding_count": len(validation_findings),
                "findings": validation_findings,
            },
            operation_results=check_result.operation_results,
            failed_guard=check_result.failed_guard,
            failed_step=check_result.failed_step,
            preflight_decision=check_result.preflight_decision,
            analysis_tree=check_result.analysis_tree,
        )

    effective_profile = profile
    active_profile_name = check_result.outputs.get("active_profile")
    if isinstance(active_profile_name, str) and available_profiles is not None and active_profile_name in available_profiles:
        effective_profile = available_profiles[active_profile_name]
    findings = _build_review_findings(
        workflow,
        check_result,
        profile=effective_profile,
        connector_provider=connector_provider,
    )
    outputs = {
        "review_status": "clean" if not findings else "needs_attention",
        "finding_count": len(findings),
        "findings": findings,
        "categories": sorted({item["category"] for item in findings if isinstance(item.get("category"), str)}),
        "check_snapshot": {
            "status": check_result.status.value,
            "allowed_state": check_result.outputs.get("allowed_state"),
            "analysis_complete": check_result.outputs.get("analysis_complete"),
            "incomplete_reasons": [
                reason for reason in check_result.outputs.get("incomplete_reasons", []) if isinstance(reason, str)
            ],
        },
        "active_profile": check_result.outputs.get("active_profile"),
    }
    return RuntimeResult(
        mode=Mode.REVIEW,
        status=RuntimeStatus.OK,
        diagnostics=check_result.diagnostics,
        plan=check_result.plan,
        outputs=outputs,
        operation_results=check_result.operation_results,
        failed_guard=check_result.failed_guard,
        failed_step=check_result.failed_step,
        preflight_decision=check_result.preflight_decision,
        analysis_tree=check_result.analysis_tree,
    )


def _build_review_findings(
    workflow: Workflow,
    check_result: RuntimeResult,
    *,
    profile: Profile | None,
    connector_provider: ConnectorProvider | None,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    findings.extend(_find_diagnostic_review_hints(check_result))
    findings.extend(_find_profile_switch_literal_string_hints(workflow))
    findings.extend(_find_missing_input_validation(workflow, check_result, profile=profile))
    findings.extend(_find_unused_declared_inputs(workflow, check_result, profile=profile))
    findings.extend(_find_missing_recommended_observations(check_result))
    findings.extend(_find_unnecessary_with_root_adapter_bindings(workflow))
    findings.extend(
        _find_bounded_fan_out_authoring_findings(
            workflow,
            check_result,
            connector_provider=connector_provider,
        )
    )
    return findings


def _find_unnecessary_with_root_adapter_bindings(workflow: Workflow) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path, expression, context in _iter_review_expression_surfaces(workflow):
        try:
            if context is LocalExpressionContext.GUARD:
                parsed = parse_condition_local_expression(expression, context=context)
            elif context is LocalExpressionContext.STEP_CONDITION:
                parsed = parse_condition_local_expression(expression, context=context)
            else:
                parsed = parse_value_local_expression(expression, context=context, allow_boolean_composition=True)
        except LocalExpressionParseError:
            continue
        for node in _iter_value_expression_nodes(parsed.value.root):
            if not isinstance(node, AdapterInvocationNode):
                continue
            root_binding = _adapter_root_only_binding(node)
            if root_binding is None:
                continue
            findings.append(
                {
                    "code": "review.workflow.adapter_pipe_style_preferred",
                    "level": "warning",
                    "category": "value_authoring",
                    "message": "Use pipe-style adapter binding instead of with{root: ...} when an equivalent pipe form exists",
                    "path": list(path),
                    "evidence": {
                        "expression": expression,
                        "adapter_expression": expression[node.start : node.end],
                        "suggested_expression": f"{render_expression_text(root_binding.value, source=parsed.source)} | {node.family}{node.body}",
                        "context": context.value,
                    },
                }
            )
    return findings


def _find_diagnostic_review_hints(check_result: RuntimeResult) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for diagnostic in check_result.diagnostics:
        if diagnostic.code not in {
            "validation.workflow.value_expr.literal_string_maybe_unquoted",
            "validation.workflow.profile_switch.literal_string_maybe_unquoted",
        }:
            continue
        findings.append(
            {
                "code": "review.workflow.literal_string_maybe_unquoted",
                "level": "warning",
                "category": "value_authoring",
                "message": diagnostic.message,
                "path": list(diagnostic.path),
                "evidence": dict(diagnostic.details),
            }
        )
    return findings


def _find_profile_switch_literal_string_hints(workflow: Workflow) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for block_index, block in enumerate(workflow.blocks):
        if not isinstance(block, StepBlock):
            continue
        for step_index, step in enumerate(block.steps):
            if not isinstance(step.profile_switch, str):
                continue
            if authored_string_style(step.profile_switch) != "plain":
                continue
            if step.profile_switch.startswith("${") and step.profile_switch.endswith("}") and len(step.profile_switch) >= 4:
                continue
            findings.append(
                {
                    "code": "review.workflow.literal_string_maybe_unquoted",
                    "level": "warning",
                    "category": "value_authoring",
                    "message": "This bare profile_switch value may be an intended literal profile name. Quote it explicitly if it should not be evaluated as an expression.",
                    "path": ["blocks", str(block_index), "steps", str(step_index), "profile_switch"],
                    "evidence": {
                        "expression": step.profile_switch,
                        "source": "workflow",
                    },
                }
            )
    return findings


def _find_bounded_fan_out_authoring_findings(
    workflow: Workflow,
    check_result: RuntimeResult,
    *,
    connector_provider: ConnectorProvider | None,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    authored_steps = _workflow_steps_by_name(workflow)
    preflight_items = [item for item in check_result.outputs.get("preflight_step_items", []) if isinstance(item, dict)]
    for item in preflight_items:
        step_name = item.get("name")
        if not isinstance(step_name, str):
            continue
        authored_step = authored_steps.get(step_name)
        if authored_step is None or authored_step.for_each is None:
            continue
        if authored_step.steps is not None:
            conditional_inner_steps = [inner.name for inner in authored_step.steps if inner.if_ is not None]
            if len(authored_step.steps) > 2 or conditional_inner_steps:
                findings.append(
                    {
                        "code": "review.workflow.fan_out.inline_body_complexity",
                        "level": "warning",
                        "category": "fan_out_authoring",
                        "message": f"Fan-out step '{step_name}' has an inline repeated body that may be too complex to keep inline",
                        "path": ["blocks", str(item.get("block_index")), "steps", str(item.get("step_index"))],
                        "evidence": {
                            "step": step_name,
                            "body_kind": item.get("body_kind"),
                            "inner_step_count": len(authored_step.steps),
                            "conditional_inner_steps": conditional_inner_steps,
                            "reason": "large or branchy inline repeated bodies are harder to review than extracted reusable fragments",
                        },
                    }
                )
        cardinality_status = _fan_out_cardinality_status(
            authored_step,
            workflow,
            check_result=check_result,
            connector_provider=connector_provider,
        )
        if cardinality_status == "runtime_only":
            findings.append(
                {
                    "code": "review.workflow.fan_out.runtime_only_cardinality",
                    "level": "warning",
                    "category": "fan_out_authoring",
                    "message": f"Fan-out step '{step_name}' has runtime-only cardinality",
                    "path": ["blocks", str(item.get("block_index")), "steps", str(item.get("step_index")), "for_each"],
                    "evidence": {
                        "step": step_name,
                        "body_kind": item.get("body_kind"),
                        "for_each": authored_step.for_each,
                        "reason": "the repeated item count cannot be determined from currently available authoring-time runtime inputs",
                    },
                }
            )
    return findings


def _workflow_steps_by_name(workflow: Workflow) -> dict[str, object]:
    return {
        step.name: step
        for block in workflow.blocks
        if isinstance(block, StepBlock)
        for step in block.steps
    }


def _workflow_steps_by_register(workflow: Workflow) -> dict[str, Step]:
    return {
        step.register: step
        for block in workflow.blocks
        if isinstance(block, StepBlock)
        for step in block.steps
        if isinstance(step.register, str)
    }


def _iter_review_expression_surfaces(workflow: Workflow) -> list[tuple[tuple[str, ...], str, LocalExpressionContext]]:
    surfaces: list[tuple[tuple[str, ...], str, LocalExpressionContext]] = []
    for name, expression in workflow.let_bindings.items():
        if isinstance(expression, str):
            surfaces.append((("let", name), expression, LocalExpressionContext.EMBEDDED_VALUE))
    for block_index, block in enumerate(workflow.blocks):
        if isinstance(block, GuardBlock):
            for guard_index, guard in enumerate(block.guards):
                if isinstance(guard.expr, str):
                    surfaces.append((("blocks", str(block_index), "guards", str(guard_index)), guard.expr, LocalExpressionContext.GUARD))
            continue
        if isinstance(block, StepBlock):
            for step_index, step in enumerate(block.steps):
                surfaces.extend(_step_expression_surfaces(step, path=("blocks", str(block_index), "steps", str(step_index))))
            continue
        if isinstance(block, RunBlock):
            if isinstance(block.if_, str):
                surfaces.append((("blocks", str(block_index), "if"), block.if_, LocalExpressionContext.STEP_CONDITION))
            surfaces.extend(_collect_value_surface_expressions(block.with_, path=("blocks", str(block_index), "with")))
    return surfaces


def _step_expression_surfaces(step: Step, *, path: tuple[str, ...]) -> list[tuple[tuple[str, ...], str, LocalExpressionContext]]:
    surfaces: list[tuple[tuple[str, ...], str, LocalExpressionContext]] = []
    if isinstance(step.if_, str):
        surfaces.append((path + ("if",), step.if_, LocalExpressionContext.STEP_CONDITION))
    surfaces.extend(_collect_native_value_surface_expressions(step.for_each, path=path + ("for_each",)))
    if step.operation is not None:
        surfaces.extend(_collect_value_surface_expressions(step.operation.with_, path=path + ("with",)))
    if step.run is not None:
        surfaces.extend(_collect_value_surface_expressions(step.run_with, path=path + ("with",)))
        surfaces.extend(_collect_value_surface_expressions(step.run_state_bindings, path=path + ("state_bindings",)))
        surfaces.extend(_collect_value_surface_expressions(step.run_states, path=path + ("states",)))
    if step.steps is not None:
        for inner_index, inner in enumerate(step.steps):
            surfaces.extend(_step_expression_surfaces(inner, path=path + ("steps", str(inner_index))))
    surfaces.extend(_collect_native_value_surface_expressions(step.profile_switch, path=path + ("profile_switch",)))
    surfaces.extend(_collect_native_value_surface_expressions(step.value, path=path + ("value",)))
    surfaces.extend(_collect_native_value_surface_expressions(step.result, path=path + ("result",)))
    surfaces.extend(_collect_native_value_surface_expressions(step.publish, path=path + ("publish",)))
    surfaces.extend(_collect_value_surface_expressions(step.state_set, path=path + ("state_set",)))
    surfaces.extend(_collect_value_surface_expressions(step.state_delete, path=path + ("state_delete",)))
    return surfaces


def _collect_native_value_surface_expressions(value: object, *, path: tuple[str, ...]) -> list[tuple[tuple[str, ...], str, LocalExpressionContext]]:
    if isinstance(value, str):
        return [(path, value, LocalExpressionContext.EMBEDDED_VALUE)]
    return _collect_value_surface_expressions(value, path=path)


def _collect_value_surface_expressions(value: object, *, path: tuple[str, ...]) -> list[tuple[tuple[str, ...], str, LocalExpressionContext]]:
    surfaces: list[tuple[tuple[str, ...], str, LocalExpressionContext]] = []
    if isinstance(value, str):
        expression = extract_embedded_local_expression(value)
        if expression is not None:
            surfaces.append((path, value, LocalExpressionContext.EMBEDDED_VALUE))
            return surfaces
        if authored_string_style(value) == "plain":
            surfaces.append((path, value, LocalExpressionContext.EMBEDDED_VALUE))
        return surfaces
    if isinstance(value, list):
        for index, item in enumerate(value):
            surfaces.extend(_collect_value_surface_expressions(item, path=path + (str(index),)))
        return surfaces
    if isinstance(value, dict):
        for key, item in value.items():
            surfaces.extend(_collect_value_surface_expressions(item, path=path + (str(key),)))
        return surfaces
    return surfaces


def _iter_value_expression_nodes(node: ValueExpressionNode) -> list[ValueExpressionNode]:
    nodes = [node]
    if isinstance(node, ListNode):
        for item in node.items:
            nodes.extend(_iter_value_expression_nodes(item))
        return nodes
    if isinstance(node, ObjectEntryNode):
        nodes.extend(_iter_value_expression_nodes(node.value))
        return nodes
    if isinstance(node, ObjectNode):
        for entry in node.entries:
            nodes.extend(_iter_value_expression_nodes(entry))
        return nodes
    if isinstance(node, CallArgumentNode):
        nodes.extend(_iter_value_expression_nodes(node.value))
        return nodes
    if isinstance(node, CallNode):
        for argument in node.arguments:
            nodes.extend(_iter_value_expression_nodes(argument))
        return nodes
    if isinstance(node, PipelineNode):
        nodes.extend(_iter_value_expression_nodes(node.source))
        for filter_node in node.filters:
            nodes.extend(_iter_value_expression_nodes(filter_node))
        return nodes
    if isinstance(node, FilterApplicationNode):
        for argument in node.arguments:
            nodes.extend(_iter_value_expression_nodes(argument))
        return nodes
    if isinstance(node, BuiltinCallNode):
        for argument in node.arguments:
            nodes.extend(_iter_value_expression_nodes(argument))
        return nodes
    if isinstance(node, UnaryNode):
        nodes.extend(_iter_value_expression_nodes(node.operand))
        return nodes
    if isinstance(node, BinaryNode):
        nodes.extend(_iter_value_expression_nodes(node.left))
        nodes.extend(_iter_value_expression_nodes(node.right))
        return nodes
    if isinstance(node, AdapterBindingNode):
        nodes.extend(_iter_value_expression_nodes(node.value))
        return nodes
    if isinstance(node, AdapterInvocationNode):
        for binding in node.bindings:
            nodes.extend(_iter_value_expression_nodes(binding))
        return nodes
    return nodes


def _adapter_root_only_binding(node: AdapterInvocationNode) -> AdapterBindingNode | None:
    if len(node.bindings) != 1:
        return None
    binding = node.bindings[0]
    return binding if binding.name == "root" else None


def _fan_out_cardinality_status(
    step,
    workflow: Workflow,
    *,
    check_result: RuntimeResult | None,
    connector_provider: ConnectorProvider | None,
) -> str:
    if step.for_each is None:
        return "not_applicable"
    for candidate_workflow, candidate_step_results in _fan_out_resolution_candidates(workflow, check_result):
        try:
            value = resolve_runtime_value(
                step.for_each,
                candidate_workflow,
                step_results=candidate_step_results,
                allow_boolean_composition=True,
            )
        except ValueResolutionError:
            continue
        if isinstance(value, list):
            return "static_known"
    if _fan_out_cardinality_review_derivable(
        step.for_each,
        workflow,
        check_result,
        connector_provider=connector_provider,
    ):
        return "review_known"
    return "runtime_only"


def _fan_out_resolution_candidates(
    workflow: Workflow,
    check_result: RuntimeResult | None,
) -> list[tuple[Workflow, dict[str, object] | None]]:
    candidates: list[tuple[Workflow, dict[str, object] | None]] = []
    if check_result is not None:
        analysis_tree = getattr(check_result, "analysis_tree", None)
        analysis_workflow = getattr(analysis_tree, "workflow", None)
        if isinstance(analysis_workflow, Workflow):
            candidates.append((analysis_workflow, None))
        preflight_step_results = check_result.outputs.get("preflight_step_results")
        if isinstance(preflight_step_results, dict):
            candidates.append((workflow, preflight_step_results))
    candidates.append((workflow, None))
    return candidates


def _fan_out_cardinality_review_derivable(
    expression: object,
    workflow: Workflow,
    check_result: RuntimeResult | None,
    *,
    connector_provider: ConnectorProvider | None,
) -> bool:
    if not isinstance(expression, str) or check_result is None:
        return False
    resolved_provider = connector_provider
    if resolved_provider is None:
        try:
            resolved_provider = get_default_connector_provider()
        except RuntimeError:
            return False
    try:
        parsed = parse_value_local_expression(expression, allow_boolean_composition=True)
    except LocalExpressionParseError:
        return False
    step_references = [node for node in _iter_value_expression_nodes(parsed.value.root) if isinstance(node, StepReferenceNode)]
    if len(step_references) != 1:
        return False
    source_step = _workflow_steps_by_register(workflow).get(step_references[0].register)
    if source_step is None or source_step.operation is None:
        return False
    preflight_items = [item for item in check_result.outputs.get("preflight_step_items", []) if isinstance(item, dict)]
    source_item = next((item for item in preflight_items if item.get("name") == source_step.name), None)
    if not isinstance(source_item, dict) or source_item.get("preflight_classification") != "read_only_analyzable":
        return False
    return _step_reference_reads_collection_output(
        step_references[0],
        source_step=source_step,
        connector_provider=resolved_provider,
    )


def _step_reference_reads_collection_output(
    step_reference: StepReferenceNode,
    *,
    source_step: Step,
    connector_provider: ConnectorProvider,
) -> bool:
    if step_reference.fields == ("results",) and (source_step.run is not None or source_step.steps is not None):
        return True
    if not step_reference.fields or step_reference.fields[0] != "outputs" or source_step.operation is None:
        return False
    operation = connector_provider.registry.get_operation(source_step.operation.uses)
    if operation is None:
        return False
    output_value: object = operation.outputs
    for field in step_reference.fields[1:]:
        if isinstance(output_value, list):
            if not output_value:
                return False
            output_value = output_value[0]
        if not isinstance(output_value, dict) or field not in output_value:
            return False
        output_value = output_value[field]
    return isinstance(output_value, list)


def _find_missing_input_validation(
    workflow: Workflow,
    check_result: RuntimeResult,
    *,
    profile: Profile | None,
) -> list[dict[str, object]]:
    input_usages = _input_usages_from_result(check_result)
    if not input_usages:
        return []

    analysis_workflow = getattr(check_result, "analysis_tree", None)
    guard_workflow = workflow
    if analysis_workflow is not None and hasattr(analysis_workflow, "workflow") and isinstance(analysis_workflow.workflow, Workflow):
        guard_workflow = analysis_workflow.workflow

    early_guard_expressions: list[str] = []
    for block in guard_workflow.blocks:
        if isinstance(block, GuardBlock):
            early_guard_expressions.extend(guard.reference for guard in block.guards if isinstance(guard.reference, str))

    findings: list[dict[str, object]] = []
    for usage in input_usages:
        input_name = usage.get("input")
        if not isinstance(input_name, str):
            continue
        classification = _review_input_classification(usage, workflow=workflow, profile=profile)
        if classification in {"ambient_profile_context", "trusted_profile_input"}:
            continue
        if classification not in {"control_input", "effect_target_input", "contract_input"}:
            continue
        needle = f"inputs.{input_name}"
        if any(needle in expression for expression in early_guard_expressions):
            continue
        findings.append(
            {
                "code": "review.workflow.input_validation_missing",
                "level": "warning",
                "category": "input_validation",
                "message": f"Input '{input_name}' is not validated in early guards",
                "path": ["inputs", input_name],
                "evidence": {
                    "input": input_name,
                    "classification": classification,
                    "usage_sites": [dict(site) for site in usage.get("evidence", []) if isinstance(site, dict)],
                    "reason": "no early guard references this input before step execution begins",
                },
            }
        )
    return findings


def _input_usages_from_result(check_result: RuntimeResult) -> list[dict[str, object]]:
    analysis_tree = getattr(check_result, "analysis_tree", None)
    if analysis_tree is None or not hasattr(analysis_tree, "input_usages"):
        return []
    return [dict(item) for item in getattr(analysis_tree, "input_usages") if isinstance(item, dict)]


def _review_input_classification(usage: dict[str, object], *, workflow: Workflow | None = None, profile: Profile | None) -> str:
    base = usage.get("classification")
    input_name = usage.get("input")
    if not isinstance(base, str) or not isinstance(input_name, str):
        return "unknown"
    if workflow is not None and input_name in workflow.explicit_input_keys:
        return base
    if profile is not None and input_name in profile.inputs and base in {"effect_target_input", "contract_input"}:
        return "trusted_profile_input"
    if profile is not None and input_name in profile.inputs and base != "control_input":
        return "ambient_profile_context"
    return base


def _find_unused_declared_inputs(workflow: Workflow, check_result: RuntimeResult, *, profile: Profile | None) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for usage in _input_usages_from_result(check_result):
        input_name = usage.get("input")
        if not isinstance(input_name, str):
            continue
        classification = _review_input_classification(usage, workflow=workflow, profile=profile)
        if classification != "unused_input":
            continue
        findings.append(
            {
                "code": "review.workflow.input_declared_but_unused",
                "level": "warning",
                "category": "input_surface",
                "message": f"Input '{input_name}' is declared but not used by the workflow",
                "path": ["inputs", input_name],
                "evidence": {
                    "input": input_name,
                    "classification": classification,
                    "usage_sites": [dict(site) for site in usage.get("evidence", []) if isinstance(site, dict)],
                    "reason": "no control, effect-target, or contract-shaping usage was found in the analyzed workflow",
                },
            }
        )
    return findings


def _find_missing_recommended_observations(check_result: RuntimeResult) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for item in check_result.outputs.get("preflight_step_items", []):
        if not isinstance(item, dict):
            continue
        support = item.get("preflight_support")
        if not isinstance(support, dict):
            continue
        strength = support.get("strength")
        missing = support.get("missing_observations")
        if strength not in {"weak", "partial"} or not isinstance(missing, list) or not missing:
            continue
        findings.append(
            {
                "code": "review.workflow.missing_recommended_observations",
                "level": "warning",
                "category": "preflight_support",
                "message": f"Step '{item.get('name')}' is missing recommended preflight observations",
                "path": ["blocks", str(item.get("block_index")), "steps", str(item.get("step_index"))],
                "evidence": {
                    "step": item.get("name"),
                    "reference": item.get("reference"),
                    "strength": strength,
                    "missing_observations": list(missing),
                },
            }
        )
    return findings
