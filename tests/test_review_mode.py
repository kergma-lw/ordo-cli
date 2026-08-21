import unittest

from ordo.model.profile import Profile
from ordo.model.runtime import Diagnostic, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import check_workflow, load_workflow_text, review_workflow
from ordo.runtime.reviewing import _review_input_classification

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ReviewModeTest(unittest.TestCase):
    def test_review_reports_missing_input_validation(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string", "unused": "string"},
            steps=(Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["review_status"], "needs_attention")
        self.assertTrue(any(item["code"] == "review.workflow.input_validation_missing" for item in result.outputs["findings"]))
        validation = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.input_validation_missing")
        self.assertEqual(validation["evidence"]["classification"], "effect_target_input")
        self.assertEqual(validation["evidence"]["suggested_fix"], "add_early_guard_validation")
        self.assertEqual(validation["evidence"]["suggested_rewrite"], {"guards": ["inputs.repository"]})

    def test_review_reports_hint_for_likely_unquoted_literal_string(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: publish-demo
blocks:
  - guards: []
  - steps:
      - name: publish
        publish:
          summary: done
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.outputs["review_status"], "unavailable")
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.literal_string_maybe_unquoted")
        self.assertEqual(finding["evidence"]["suggested_fix"], "quote_literal_string")
        self.assertEqual(finding["evidence"]["suggested_rewrite"], '"done"')

    def test_review_reports_hint_for_likely_unquoted_profile_switch_literal(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: switch-demo
blocks:
  - steps:
      - name: switch
        profile_switch: meta
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["review_status"], "needs_attention")
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.literal_string_maybe_unquoted")
        self.assertEqual(finding["path"], ["blocks", "0", "steps", "0", "profile_switch"])
        self.assertEqual(finding["evidence"]["expression"], "meta")
        self.assertEqual(finding["evidence"]["suggested_fix"], "quote_literal_string")
        self.assertEqual(finding["evidence"]["suggested_rewrite"], '"meta"')

    def test_review_reports_unused_declared_input_separately(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string", "unused": "string"},
            steps=(Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        unused = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.input_declared_but_unused")
        self.assertEqual(unused["path"], ["inputs", "unused"])
        self.assertEqual(unused["evidence"]["classification"], "unused_input")

    def test_review_reports_workflow_profile_as_project_local_binding(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            profile="frontend",
            steps=(Step(name="inspect", operation=OperationRef("gh.issue")),),
        )
        profiles = {"frontend": Profile(name="frontend")}

        result = review_workflow(workflow, available_profiles=profiles, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.profile.project_local_binding")
        self.assertEqual(finding["path"], ["profile"])
        self.assertEqual(finding["evidence"]["binding_scope"], "current_workflow_and_descendant_runs")

    def test_review_counts_input_used_inside_adapter_outer_binding(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: yaml-adapter-demo
inputs:
  body:
    type: string
blocks:
  - steps:
      - name: extract-name
        value: 'yaml.user.name with{root: inputs.body}'
        register: extracted
      - name: publish-name
        publish:
          name: step.extracted.outputs.value
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(any(item["code"] == "review.workflow.input_declared_but_unused" for item in result.outputs["findings"]))

    def test_review_reports_unnecessary_with_root_when_pipe_equivalent_exists(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: markdown-adapter-demo
inputs:
  body:
    type: string
blocks:
  - steps:
      - name: extract-tasks
        value: 'markdown["Tasks"] with{root: inputs.body}'
        register: extracted
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.adapter_pipe_style_preferred")
        self.assertEqual(finding["path"], ["blocks", "0", "steps", "0", "value"])
        self.assertEqual(finding["evidence"]["suggested_expression"], 'inputs.body | markdown["Tasks"]')
        self.assertEqual(finding["evidence"]["suggested_rewrite"], 'inputs.body | markdown["Tasks"]')

    def test_review_reports_unnecessary_with_root_for_adapter_path_suffix(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: markdown-adapter-demo
inputs:
  body:
    type: string
blocks:
  - steps:
      - name: extract-task-refs
        value: '${markdown["Tasks"].list_items with{root: inputs.body}}'
        register: extracted
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.adapter_pipe_style_preferred")
        self.assertEqual(finding["path"], ["blocks", "0", "steps", "0", "value"])
        self.assertEqual(finding["evidence"]["suggested_expression"], 'inputs.body | markdown["Tasks"].list_items')
        self.assertEqual(finding["evidence"]["suggested_rewrite"], 'inputs.body | markdown["Tasks"].list_items')

    def test_review_does_not_report_with_root_when_additional_bindings_exist(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: json-adapter-demo
inputs:
  body:
    type: string
  kind:
    type: string
blocks:
  - steps:
      - name: extract-name
        value: 'json.items.one(kind=target_kind).name with{root: inputs.body, target_kind: inputs.kind}'
        register: extracted
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(any(item["code"] == "review.workflow.adapter_pipe_style_preferred" for item in result.outputs["findings"]))

    def test_review_counts_inputs_used_inside_structured_if_leaves(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: markdown-if-demo
inputs:
  enabled:
    type: boolean
blocks:
  - steps:
      - name: extract-tasks
        if:
          - inputs.enabled
        uses: shell.command
        with:
          command: "printf executed"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(any(item["code"] == "review.workflow.input_declared_but_unused" for item in result.outputs["findings"]))

    def test_review_recommends_structured_if_for_long_string_condition(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: readiness-check
inputs:
  a:
    type: boolean
  b:
    type: boolean
  c:
    type: boolean
  d:
    type: boolean
blocks:
  - steps:
      - name: gate
        if: inputs.a and inputs.b and inputs.c and inputs.d
        uses: shell.command
        with:
          command: "printf ok"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.step_condition.structured_form_preferred")
        self.assertEqual(finding["path"], ["blocks", "0", "steps", "0", "if"])
        self.assertEqual(finding["evidence"]["predicate_count"], 4)
        self.assertEqual(finding["evidence"]["boolean_operators"], ["and"])
        self.assertEqual(
            finding["evidence"]["suggested_rewrite"],
            ["inputs.a", "inputs.b", "inputs.c", "inputs.d"],
        )

    def test_review_recommends_structured_if_for_mixed_boolean_string_condition(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: readiness-check
inputs:
  a:
    type: boolean
  b:
    type: boolean
  c:
    type: boolean
blocks:
  - steps:
      - name: gate
        if: inputs.a and (inputs.b or inputs.c)
        uses: shell.command
        with:
          command: "printf ok"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.step_condition.structured_form_preferred")
        self.assertTrue(finding["evidence"]["has_mixed_boolean_operators"])
        self.assertEqual(
            finding["evidence"]["suggested_rewrite"],
            ["inputs.a", {"any": ["inputs.b", "inputs.c"]}],
        )

    def test_review_does_not_recommend_structured_if_for_structured_condition(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: readiness-check
inputs:
  a:
    type: boolean
  b:
    type: boolean
  c:
    type: boolean
  d:
    type: boolean
blocks:
  - steps:
      - name: gate
        if:
          - inputs.a
          - inputs.b
          - inputs.c
          - inputs.d
        uses: shell.command
        with:
          command: "printf ok"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(any(item["code"] == "review.workflow.step_condition.structured_form_preferred" for item in result.outputs["findings"]))

    def test_review_recommends_gate_for_runtime_readiness_if_on_mutating_step(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: readiness-check
blocks:
  - steps:
      - name: observed-a
        value: true
        register: observed_a
      - name: observed-b
        value: true
        register: observed_b
      - name: mutate
        if:
          - step.observed_a.outputs.value
          - step.observed_b.outputs.value
        uses: shell.command
        with:
          command: "printf ok"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.step_gate.preferred_for_readiness_check")
        self.assertEqual(finding["path"], ["blocks", "0", "steps", "2", "if"])

    def test_review_recommends_structured_form_for_long_string_gate(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: readiness-check
blocks:
  - steps:
      - name: observed-a
        value: true
        register: observed_a
      - name: observed-b
        value: true
        register: observed_b
      - name: observed-c
        value: true
        register: observed_c
      - name: observed-d
        value: true
        register: observed_d
      - name: mutate
        gate: step.observed_a.outputs.value and step.observed_b.outputs.value and step.observed_c.outputs.value and step.observed_d.outputs.value
        uses: shell.command
        with:
          command: "printf ok"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.step_condition.structured_form_preferred")
        self.assertEqual(finding["path"], ["blocks", "0", "steps", "4", "gate"])

    def test_review_recommends_guard_for_first_step_if_using_pre_step_facts(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: maybe-run
blocks:
  - steps:
      - name: mutate
        if: inputs.enabled and state.shared_state[inputs.mode_key] == "ready"
        uses: shell.command
        with:
          command: "printf ok"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.guard.preferred_for_first_step_applicability")
        self.assertEqual(finding["path"], ["blocks", "0", "steps", "0", "if"])
        self.assertEqual(finding["evidence"]["condition_roots"], ["inputs", "state"])
        self.assertFalse(finding["evidence"]["contains_step_root"])
        self.assertTrue(finding["evidence"]["first_effectful_action"])

    def test_review_does_not_recommend_guard_for_first_step_if_using_step_root(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: maybe-run
blocks:
  - steps:
      - name: observe
        value: true
        register: observed
      - name: mutate
        if: step.observed.outputs.value
        uses: shell.command
        with:
          command: "printf ok"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertFalse(any(item["code"] == "review.workflow.guard.preferred_for_first_step_applicability" for item in result.outputs["findings"]))

    def test_review_still_recommends_guard_even_when_other_guards_exist(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: maybe-run
guards:
  - inputs.ticket
blocks:
  - steps:
      - name: mutate
        if: inputs.enabled
        uses: shell.command
        with:
          command: "printf ok"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertTrue(any(item["code"] == "review.workflow.guard.preferred_for_first_step_applicability" for item in result.outputs["findings"]))

    def test_review_does_not_recommend_guard_after_earlier_effectful_action(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: maybe-run
blocks:
  - steps:
      - name: comment-first
        uses: shell.command
        with:
          command: "printf first"
      - name: mutate-later
        if: inputs.enabled
        uses: shell.command
        with:
          command: "printf second"
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertFalse(any(item["code"] == "review.workflow.guard.preferred_for_first_step_applicability" for item in result.outputs["findings"]))

    def test_review_counts_for_each_input_usage_inside_inline_profile_switch(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: profile-switch-inline-probe
inputs:
  profiles: []
blocks:
  - guards:
      - git.repo.exists
  - steps:
      - name: Validate profiles inline
        for_each: inputs.profiles
        steps:
          - name: Switch runtime profile inline
            profile_switch: ${item}
'''
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        codes = [item["code"] for item in result.outputs["findings"]]
        self.assertNotIn("review.workflow.input_declared_but_unused", codes)
        self.assertNotIn("review.workflow.input_validation_missing", codes)

    def test_review_reports_missing_recommended_probe_coverage(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "acme/repo", "issue_number": 7, "project_id": "PVT_demo"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "${inputs.repository}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "Status",
                                    "option": "In review",
                                },
                            ),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.missing_recommended_probe_coverage")
        self.assertIn("prefer explicit guard probes", finding["message"])
        self.assertEqual(finding["evidence"]["preferred_fix_kind"], "guard_probe")
        self.assertEqual(finding["evidence"]["fallback_fix_kinds"], ["read_only_probe_step"])
        self.assertEqual(finding["evidence"]["suggested_fix"], "add_guard_probes")
        self.assertTrue(finding["evidence"]["suggested_rewrite"]["guards"])

    def test_review_recognizes_recommended_probe_coverage_from_let_bound_guard_probes(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="close-story",
            declared_inputs={"repository": {}, "issue_number": {}, "project_id": {}},
            let_bindings={
                "story_project_issue": "gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id)"
            },
            blocks=(
                GuardBlock(
                    guards=(
                        Guard(expr="story_project_issue.exists"),
                        Guard(expr='gh.project.field(project_id=inputs.project_id, field="Status").exists'),
                        Guard(expr='gh.project.field.option(project_id=inputs.project_id, field="Status", option="Done").exists'),
                    )
                ),
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "${inputs.repository}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "Status",
                                    "option": "Done",
                                },
                            ),
                        ),
                    )
                ),
            ),
            inputs={"repository": "acme/repo", "issue_number": 7, "project_id": "PVT_demo"},
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(any(item["code"] == "review.workflow.missing_recommended_probe_coverage" for item in result.outputs["findings"]))

    def test_review_reports_unmaterialized_probe_coverage_separately_from_missing_coverage(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="close-story",
            declared_inputs={"repository": {}, "issue_number": {}, "project_id": {}},
            let_bindings={
                "story_project_issue": "gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id)",
                "status_field": 'gh.project.field(project_id=inputs.project_id, field="Status")',
                "done_option": 'gh.project.field.option(project_id=inputs.project_id, field="Status", option="Done")',
            },
            blocks=(
                GuardBlock(
                    guards=(
                        Guard(expr="story_project_issue.exists"),
                        Guard(expr="status_field.exists"),
                        Guard(expr="done_option.exists"),
                    )
                ),
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "${inputs.repository}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "Status",
                                    "option": "Done",
                                },
                            ),
                        ),
                    )
                ),
            ),
            inputs={"repository": "acme/repo", "issue_number": 7, "project_id": "PVT_demo"},
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "gh.project.issue":
                return OperationResult(status="probe_failed", diagnostics=(Diagnostic(code="probe.failed", level="error", message="boom", path=()),))
            outputs = {
                "gh.project.field": {"exists": True},
                "gh.project.field.option": {"exists": True},
            }
            return OperationResult(status="ok", outputs=outputs[resolved_guard.reference])

        result = review_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        codes = [item["code"] for item in result.outputs["findings"]]
        self.assertNotIn("review.workflow.missing_recommended_probe_coverage", codes)
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.recommended_probe_result_not_available")
        self.assertEqual(finding["evidence"]["suggested_fix"], "make_probe_result_available")
        self.assertEqual(finding["evidence"]["unmaterialized_probes"][0]["probe"], "gh.project.issue")
        self.assertEqual(finding["evidence"]["unavailability_kind"], "current_pre_step_facts_incomplete")
        self.assertEqual(finding["evidence"]["blocking_guard"], "story_project_issue.exists")
        self.assertIn("gh.project.issue(", finding["evidence"]["blocking_expression"])

    def test_check_publishes_successful_guard_probe_observations_from_let_expansion(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="close-story",
            declared_inputs={"repository": {}, "issue_number": {}, "project_id": {}},
            let_bindings={
                "story_project_issue": "gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id)"
            },
            blocks=(
                GuardBlock(
                    guards=(
                        Guard(expr="story_project_issue.exists"),
                    )
                ),
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "${inputs.repository}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "Status",
                                    "option": "Done",
                                },
                            ),
                        ),
                    )
                ),
            ),
            inputs={"repository": "acme/repo", "issue_number": 7, "project_id": "PVT_demo"},
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        guard_detail = result.outputs["guard_details"][0]
        self.assertTrue(guard_detail["authored_probes"])
        self.assertEqual(guard_detail["authored_probes"][0]["probe"], "gh.project.issue")
        self.assertEqual(guard_detail["authored_probes"][0]["fields"], ["exists"])
        self.assertEqual(guard_detail["probes"], [])

    def test_review_recognizes_recommended_probe_coverage_from_guard_probes_with_bare_input_references(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="task-to-ready",
            let_bindings={
                "project_issue": "gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id)",
                "status_field": 'gh.project.field(project_id=inputs.project_id, field="Status")',
                "ready_option": 'gh.project.field.option(project_id=inputs.project_id, field="Status", option="Ready")',
            },
            blocks=(
                GuardBlock(
                    guards=(
                        Guard(expr="project_issue.exists"),
                        Guard(expr="status_field.exists"),
                        Guard(expr="ready_option.exists"),
                    )
                ),
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "inputs.repository",
                                    "issue_number": "inputs.issue_number",
                                    "project_id": "inputs.project_id",
                                    "field": "Status",
                                    "option": "Ready",
                                },
                            ),
                        ),
                    )
                ),
            ),
            inputs={"repository": "acme/repo", "issue_number": 7, "project_id": "PVT_demo"},
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(any(item["code"] == "review.workflow.missing_recommended_probe_coverage" for item in result.outputs["findings"]))

    def test_review_reports_clean_when_no_findings_exist(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string"},
            blocks=(
                GuardBlock(guards=(Guard(expr="inputs.repository | is_string"),)),
                StepBlock(
                    steps=(
                        Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),
                    )
                ),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["review_status"], "clean")
        self.assertEqual(result.outputs["finding_count"], 0)
        self.assertEqual(result.outputs["findings"], [])

    def test_review_reports_inline_fan_out_complexity(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-many",
            inputs={"items": ["one", "two"]},
            steps=(
                Step(
                    name="inspect",
                    for_each="${inputs.items}",
                    steps=(
                        Step(name="capture", value="${item}", register="item_value"),
                        Step(name="copy", value="${step.item_value.outputs.value}", register="copied"),
                        Step(name="publish", result={"summary": "${step.copied.outputs.value}"}, if_="step.copied.outputs.value"),
                    ),
                    register="runs",
                ),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.fan_out.inline_body_complexity")
        self.assertEqual(finding["evidence"]["body_kind"], "inline_repeated_steps")
        self.assertEqual(finding["evidence"]["inner_step_count"], 3)
        self.assertEqual(finding["evidence"]["suggested_fix"], "extract_reusable_fan_out_fragment")
        self.assertEqual(finding["evidence"]["suggested_rewrite"]["step"]["run"], "<fragment-path>")

    def test_review_reports_runtime_only_fan_out_cardinality(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-many",
            steps=(
                Step(name="load-items", operation=OperationRef("gh.issue"), register="items"),
                Step(
                    name="inspect",
                    for_each="${step.items.outputs.items}",
                    steps=(Step(name="capture", value="${item}", register="item_value"),),
                    register="runs",
                ),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.fan_out.runtime_only_cardinality")
        self.assertEqual(finding["path"][-1], "for_each")
        self.assertEqual(finding["evidence"]["suggested_fix"], "materialize_or_declare_fan_out_collection")
        self.assertEqual(finding["evidence"]["suggested_rewrite"]["before"]["register"], "items")

    def test_review_does_not_report_runtime_only_fan_out_when_source_is_review_derivable_collection(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-many",
            steps=(
                Step(
                    name="load-items",
                    operation=OperationRef("gh.project.items", with_={"project_id": "PVT_demo"}),
                    register="items",
                ),
                Step(
                    name="inspect",
                    run="fragment.yml",
                    for_each='step.items.outputs.items | field("id")',
                    register="runs",
                ),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertFalse(any(item["code"] == "review.workflow.fan_out.runtime_only_cardinality" for item in result.outputs["findings"]))

    def test_review_keeps_simple_inline_fan_out_clean(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-many",
            inputs={"items": ["one", "two"]},
            steps=(
                Step(
                    name="inspect",
                    for_each="${inputs.items}",
                    steps=(Step(name="capture", value="${item}", register="item_value"),),
                    register="runs",
                ),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertFalse(any(item["code"].startswith("review.workflow.fan_out.") for item in result.outputs["findings"]))

    def test_review_ignores_profile_carried_ambient_context_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="set-active-profile",
            declared_inputs={
                "active_profile_key": {},
                "profile": {},
                "repo_kind": {},
                "repo_dir": {},
                "repository": {},
                "project_id": {},
            },
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.profile == "frontend" or inputs.profile == "backend" or inputs.profile == "meta"'),)),
                StepBlock(
                    steps=(
                        Step(name="Switch runtime profile", profile_switch="${inputs.profile}"),
                        Step(name="Remember active profile", state_set={"state.shared[inputs.active_profile_key]": "${inputs.profile}"}),
                    )
                ),
            ),
        )
        profile = Profile(
            name="backend",
            inputs={
                "repo_kind": "backend",
                "repo_dir": "/tmp/backend",
                "repository": "acme/backend",
                "project_id": "PVT_demo",
            },
        )

        result = review_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        messages = [item["message"] for item in result.outputs["findings"]]
        self.assertTrue(any("active_profile_key" in message for message in messages))
        self.assertFalse(any("repo_kind" in message for message in messages))
        self.assertFalse(any("repo_dir" in message for message in messages))
        self.assertFalse(any("repository" in message for message in messages))
        self.assertFalse(any("project_id" in message for message in messages))

    def test_review_classifies_profile_provided_consumed_inputs_as_trusted(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="issue-view",
            declared_inputs={"profile": {}, "number": {}, "repository": {}, "project_id": {}},
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.profile == "backend"'), Guard(expr="inputs.number | is_integer"))),
                StepBlock(
                    steps=(
                        Step(name="load issue", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": "${inputs.number}"})),
                        Step(name="publish", publish={"repository": "${inputs.repository}", "project_id": "${inputs.project_id}"}),
                    )
                ),
            ),
        )
        profile = Profile(
            name="backend",
            inputs={
                "repository": "acme/backend",
                "project_id": "PVT_demo",
            },
        )

        result = review_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        all_classifications = {
            item["input"]: item["classification"]
            for item in result.analysis_tree.input_usages
        }
        self.assertEqual(all_classifications["repository"], "contract_input")
        repository_usage = next(item for item in result.analysis_tree.input_usages if item["input"] == "repository")
        project_usage = next(item for item in result.analysis_tree.input_usages if item["input"] == "project_id")
        self.assertEqual(_review_input_classification(repository_usage, profile=profile), "trusted_profile_input")
        self.assertEqual(_review_input_classification(project_usage, profile=profile), "trusted_profile_input")
        self.assertEqual(result.status, RuntimeStatus.OK)

    def test_review_does_not_warn_for_trusted_profile_provided_consumed_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="issue-view",
            declared_inputs={"profile": {}, "number": {}, "repository": {}, "project_id": {}},
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.profile == "backend"'), Guard(expr="inputs.number | is_integer"))),
                StepBlock(
                    steps=(
                        Step(name="load issue", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": "${inputs.number}"})),
                        Step(name="publish", publish={"repository": "${inputs.repository}", "project_id": "${inputs.project_id}"}),
                    )
                ),
            ),
        )
        profile = Profile(name="backend", inputs={"repository": "acme/backend", "project_id": "PVT_demo"})

        result = review_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertFalse(any(item["code"] == "review.workflow.input_validation_missing" for item in result.outputs["findings"]))

    def test_review_keeps_missing_validation_for_user_driven_effect_target_input(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string"},
            steps=(Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertTrue(any(item["code"] == "review.workflow.input_validation_missing" for item in result.outputs["findings"]))
