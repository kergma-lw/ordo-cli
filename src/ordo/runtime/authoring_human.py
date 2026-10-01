"""Reader-facing projection for runtime-owned workflow authoring rules."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.model.human import HumanDeclaration, declare_human


def workflow_rules_human(rules: list[JSONObject]) -> HumanDeclaration:
    """Keep rule navigation separate from the full validation declaration."""

    return declare_human({
        "title": "Workflow rules",
        "goal": "Author workflows that are explicit, reviewable, and safe to validate before execution.",
        "summary": "Use these rules when adding, changing, or reviewing workflow authoring choices.",
        "sections": [
            {"heading": "Default loop", "items": ["After changing a workflow, run both check and review.", "Declare applicability and validate inputs near the start.", "Keep published outputs small and intentional."]},
            {"heading": "Rules", "subsections": [_rule_human(rule) for rule in rules]},
        ],
    })


def workflow_rule_focused_describe_human(rule: JSONObject) -> HumanDeclaration | None:
    """Return the reader guide for one focused workflow rule."""

    name = rule.get("name")
    if not isinstance(name, str):
        return None
    projection = _rule_human(rule)
    return declare_human({
        "title": str(projection["heading"]),
        "goal": "Apply this workflow authoring rule when making the matching design choice.",
        "summary": str(projection["body"]),
        "sections": [
            {"heading": "Technical identifier", "items": [f"`workflow-rules.{name}`"]},
            *_focused_rule_sections(rule),
        ],
    })


def workflow_rules_focused_describe_human(rules: list[JSONObject]) -> dict[str, HumanDeclaration]:
    """Return source-owned reader guides indexed by focused workflow-rule handle."""

    guides: dict[str, HumanDeclaration] = {}
    for rule in rules:
        name = rule.get("name")
        human = workflow_rule_focused_describe_human(rule)
        if not isinstance(name, str) or human is None:
            continue
        guides[f"workflow-rules.{name}"] = human
    return guides


WORKFLOW_RULE_EXAMPLE_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "workflow-rules.example.inline_fan_out_inner_if": declare_human({
        "title": "Inline fan-out inner condition", "goal": "Make one inner repeated step optional for each current item.",
        "summary": "The inner `if` reads `item`, so each iteration decides independently.",
        "sections": [{"heading": "Author shape", "examples": ["```yaml\n- name: notify\n  for_each: inputs.issues\n  steps:\n    - name: comment\n      if: is_present(item.comment)\n      uses: gh.issue.comment.add\n      with:\n        issue_number: item.number\n        body: item.comment\n```"]}, {"heading": "Boundary", "items": ["Keep the outer `if` for whole-invocation optionality; this inner form is only for item-local work."]}, {"heading": "Related surfaces", "references": [{"handle": "workflow.step.if", "summary": "Use a step condition for item-local optional work."}, {"handle": "workflow.run.for_each", "summary": "Supply the collection that defines each repeated item."}, {"handle": "workflow-rules.fan_out_scope_and_conditions", "summary": "Apply the fan-out scope and condition rule."}]}],
    }),
    "workflow-rules.example.inline_fan_out_local_steps": declare_human({
        "title": "Inline fan-out body", "goal": "Repeat a short local body without creating a reusable target.",
        "summary": "Pair `for_each` with `steps` when each item needs a small visible sequence.",
        "sections": [{"heading": "Author shape", "examples": ["```yaml\n- name: comment on issues\n  for_each: inputs.issue_numbers\n  steps:\n    - name: add comment\n      uses: gh.issue.comment.add\n      with:\n        issue_number: item\n        body: inputs.comment\n```"]}, {"heading": "Boundary", "items": ["Move a large, reusable, or guarded body behind a named `run` target."]}, {"heading": "Related surfaces", "references": [{"handle": "workflow.run.for_each", "summary": "Supply the collection for the inline body."}, {"handle": "workflow.run.steps", "summary": "Author the repeated inline step list."}, {"handle": "workflow-rules.run_target_vs_inline_fan_out", "summary": "Choose between an inline body and a named target."}]}],
    }),
    "workflow-rules.example.named_run_target_fan_out": declare_human({
        "title": "Named target fan-out", "goal": "Repeat a reusable target with explicit arguments.",
        "summary": "Use `run`, `with`, and `for_each` when the repeated body deserves its own identity.",
        "sections": [{"heading": "Author shape", "examples": ["```yaml\n- name: inspect issues\n  run: inspect-issue\n  for_each: inputs.issue_numbers\n  with:\n    issue_number: item\n  register: inspections\n```"]}, {"heading": "Boundary", "items": ["The target receives the explicit binding as `args.issue_number`; it does not read the caller's item directly."]}, {"heading": "Related surfaces", "references": [{"handle": "workflow.run.run", "summary": "Name the reusable target to invoke."}, {"handle": "workflow.run.with", "summary": "Bind each current item to the target argument."}, {"handle": "workflow-rules.run_target_vs_inline_fan_out", "summary": "Choose a named target when the body needs its own identity."}]}],
    }),
    "workflow-rules.example.routine_env_custom_name_not_supported": declare_human({
        "title": "Routine environment naming boundary", "goal": "Forward routine context without inventing environment-variable names.",
        "summary": "Routine environment names are generated from the approved reference path.",
        "sections": [{"heading": "Author shape", "examples": ["```yaml\nwith:\n  env:\n    - inputs.profile\n```"]}, {"heading": "Boundary", "items": ["Do not write a custom name such as `PROFILE: inputs.profile`; pass only approved scalar references."]}, {"heading": "Related surfaces", "references": [{"handle": "routine_contract.workflow_call.env", "summary": "Read the routine environment forwarding contract."}, {"handle": "workflow-rules.routine.*", "summary": "Apply the boundary for using a routine at all."}]}],
    }),
    "workflow-rules.example.routine_env_non_scalar_rejected": declare_human({
        "title": "Routine scalar environment boundary", "goal": "Forward only scalar routine context.",
        "summary": "Objects and lists are rejected instead of being silently serialized into environment values.",
        "sections": [{"heading": "Author shape", "examples": ["```yaml\nwith:\n  env:\n    - inputs.profile\n    - step.collect.outputs.value.path\n```"]}, {"heading": "Boundary", "items": ["Do not forward `inputs.labels` or another object/list; pass a declared routine argument when structured data is required."]}, {"heading": "Related surfaces", "references": [{"handle": "routine_contract.workflow_call.env", "summary": "Read the allowed scalar environment reference shape."}, {"handle": "routine_contract.workflow_call.args", "summary": "Pass structured routine input through declared arguments instead."}]}],
    }),
    "workflow-rules.example.routine_env_scalar_forwarding": declare_human({
        "title": "Routine scalar environment forwarding", "goal": "Forward a short explicit list of scalar context values to a routine.",
        "summary": "The routine call names the references and generated environment names carry their scalar values.",
        "sections": [{"heading": "Author shape", "examples": ["```yaml\n- name: run local check\n  uses: routine.project-check\n  with:\n    args:\n      target: inputs.issue_number\n    env:\n      - inputs.profile\n      - step.collect.outputs.value.path\n```"]}, {"heading": "Boundary", "items": ["Use `args` for the routine's business input and keep `env` limited to required scalar context."]}, {"heading": "Related surfaces", "references": [{"handle": "routine_contract.workflow_call.args", "summary": "Supply declared routine arguments."}, {"handle": "routine_contract.workflow_call.env", "summary": "Forward only required scalar context."}, {"handle": "workflow-rules.routine.*", "summary": "Apply the narrow routine-use boundary."}]}],
    }),
}


_RULE_RELATED_SURFACES: dict[str, tuple[str, ...]] = {
    "paired_check_review_passes": ("command-line.ordo-playbook", "workflow-rules.early_guards"),
    "workflow_profile_binding_is_project_local": ("workflow.profile", "workflow.step.profile_switch"),
    "minimal_publish_payload": ("workflow.step.publish", "workflow-rules.publish_outputs"),
    "value_register_before_result": ("workflow.step.value", "workflow.step.register"),
    "decision_order": ("connector.authoring", "workflow-rules.routine.*"),
    "structured_surface_bias": ("workflow.step.uses", "workflow-rules.decision_order"),
    "shell.command": ("workflow-rules.routine.*", "workflow-rules.decision_order"),
    "routine.*": ("routine_contract", "routine_contract.workflow_call_surface"),
    "semantic_ambiguity": ("workflow-rules.decision_order", "workflow-rules.routine.*"),
    "local_artifacts_are_context": ("workflow-rules.structured_surface_bias", "workflow-rules.routine.*"),
    "early_guards": ("workflow.branching", "workflow-rules.input_validation_default"),
    "input_validation_default": ("workflow.inputs", "workflow.local_expression.filter"),
    "delegated_applicability": ("workflow.branching", "workflow-rules.early_guards"),
    "representation_adapters": ("workflow.local_expression.adapter", "workflow.local_expression.adapter_seam"),
    "guard_result_contract": ("workflow.branching", "workflow.local_expression.filter"),
    "publish_outputs": ("workflow.step.publish", "workflow.step_forms.publish"),
    "lifecycle_state": ("workflow.state_needs", "workflow.state_bindings"),
    "explicit_execution_context": ("workflow.profile", "routine_contract"),
    "separate_control_surfaces": ("workflow.branching", "workflow.step.gate"),
    "bounded_fan_out_is_structured_invocation": ("workflow.run.for_each", "workflow.step_forms.inline_fan_out_invocation"),
    "run_target_vs_inline_fan_out": ("workflow.step_forms.run_invocation", "workflow.step_forms.inline_fan_out_invocation"),
    "fan_out_scope_and_conditions": ("workflow.run.for_each", "workflow.step.if"),
    "inline_fan_out_invalid_shapes": ("workflow.step_forms.inline_fan_out_invocation", "workflow.step_forms.run_invocation"),
    "early_let": ("workflow.let", "workflow.local_expressions"),
    "native_expression_contexts": ("workflow.local_expressions", "workflow.local_expression.filter"),
}


_RULE_HEADINGS: dict[str, str] = {
    "paired_check_review_passes": "Use both check and review",
    "workflow_profile_binding_is_project_local": "Keep workflow profiles project-local",
    "minimal_publish_payload": "Publish only the result callers need",
    "value_register_before_result": "Stage reusable values before results",
    "decision_order": "Choose the most structured surface first",
    "structured_surface_bias": "Prefer structured workflow surfaces",
    "shell.command": "Avoid new shell commands",
    "routine.*": "Use routines only as a narrow fallback",
    "semantic_ambiguity": "Clarify semantic ambiguity",
    "local_artifacts_are_context": "Treat local artifacts as context",
    "early_guards": "Declare applicability early",
    "input_validation_default": "Validate inputs by default",
    "delegated_applicability": "Do not defer applicability to actions",
    "representation_adapters": "Use representation adapters for transformations",
    "guard_result_contract": "Make guard decisions boolean",
    "publish_outputs": "Publish intentional outward results",
    "lifecycle_state": "Keep lifecycle state small",
    "explicit_execution_context": "Make execution context explicit",
    "separate_control_surfaces": "Give each control surface one job",
    "bounded_fan_out_is_structured_invocation": "Keep fan-out as structured invocation",
    "run_target_vs_inline_fan_out": "Choose named targets for substantial fan-out",
    "fan_out_scope_and_conditions": "Keep fan-out scope and conditions explicit",
    "inline_fan_out_invalid_shapes": "Stay within the inline fan-out shape",
    "early_let": "Name important expressions early",
    "native_expression_contexts": "Use native expression contexts directly",
}


def _rule_human(rule: JSONObject) -> JSONObject:
    """Keep the complete reader guidance beside the runtime rule projection."""

    reader_rule = str(rule["rule"])
    why = list(rule.get("why", []))
    prefer = list(rule.get("prefer", []))
    avoid = list(rule.get("avoid", []))
    if rule.get("name") == "routine.*":
        reader_rule = "Use routine.* only for a narrow project-local task after published operations and clear compositions do not fit."
        why = ["A routine can hide product behavior that belongs in a published workflow surface.", "Frequent routine use is a signal to discuss a richer published operation."]
        prefer = ["Record which published operations and compositions were considered and what small gap remains.", "Use routine.* only for a mechanical or intentionally project-local gap.", "If the gap is semantic, stop and clarify with the user.", "Keep routine usage narrow and explicit about its inputs and outputs."]
        avoid = ["Using routine.* as a first-choice tool.", "Using routine.* when a structured connector surface already exists.", "Treating routine.* as a general extension surface."]
    sections = [
        {"heading": "Why", "items": why},
        {"heading": "Prefer", "items": prefer},
        {"heading": "Avoid", "items": avoid},
    ]
    if rule.get("stop_when"):
        sections.append({"heading": "Stop when", "items": list(rule["stop_when"])})
    if rule.get("must_not_infer"):
        sections.append({"heading": "Do not infer", "items": list(rule["must_not_infer"])})
    return {
        "heading": _RULE_HEADINGS[str(rule["name"])],
        "body": reader_rule,
        "subsections": [
            *sections,
        ],
    }


def _focused_rule_sections(rule: JSONObject) -> list[JSONObject]:
    """Keep focused rule content equivalent to the published rule declaration."""

    projection = _rule_human(rule)
    sections: list[JSONObject] = [{"heading": "Rule", "items": [str(projection["body"])]}]
    sections.extend(projection["subsections"])
    handles = _RULE_RELATED_SURFACES.get(str(rule["name"]), ())
    sections.append({"heading": "Related surfaces", "references": [
        {"handle": handle, "summary": "Continue with this related authoring guide."}
        for handle in handles
    ]})
    return sections
