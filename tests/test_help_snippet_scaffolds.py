import unittest

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import validate_workflow_text
from ordo.runtime.help_snippet_scaffolds import (
    INSERTION_CONTRACTS,
    build_expression_value_scaffold,
    build_step_field_scaffold,
    build_step_fragment_scaffold,
    build_workflow_fragment_scaffold,
)


class HelpSnippetScaffoldTest(unittest.TestCase):
    def test_insertion_contracts_publish_supported_targets(self) -> None:
        self.assertEqual(set(INSERTION_CONTRACTS.keys()), {"expression_value", "step_field", "step_fragment", "workflow_fragment", "routine_bundle"})
        self.assertIn("workflow.step.if", INSERTION_CONTRACTS["step_field"].supported_targets)
        self.assertIn("state", INSERTION_CONTRACTS["expression_value"].supported_targets)
        self.assertIn("workflow.step.if", INSERTION_CONTRACTS["step_fragment"].supported_targets)
        self.assertIn("workflow.step.state_set", INSERTION_CONTRACTS["step_fragment"].supported_targets)
        self.assertIn("workflow.profile", INSERTION_CONTRACTS["workflow_fragment"].supported_targets)
        self.assertIn("routine", INSERTION_CONTRACTS["routine_bundle"].supported_targets)

    def test_expression_value_scaffold_validates_for_state_target(self) -> None:
        workflow_text = build_expression_value_scaffold(target="state", snippet='state.shared_state["active_profile"]')

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:state")

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_expression_value_scaffold_validates_for_lookup_target(self) -> None:
        workflow_text = build_expression_value_scaffold(target="workflow.local_expression.filter.lookup", snippet='inputs.status_labels | lookup("ready")')

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:lookup")

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_step_field_scaffold_validates_for_step_if_target(self) -> None:
        workflow_text = build_step_field_scaffold(target="workflow.step.if", snippet="is_present(inputs.close_comment)")

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:step-if")

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_step_field_scaffold_validates_for_state_set_target(self) -> None:
        workflow_text = build_step_field_scaffold(target="workflow.step.state_set", snippet='state_set:\n  state.shared_state["active_profile"]: review')

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:state-set")

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_step_fragment_scaffold_validates_for_state_set_target(self) -> None:
        workflow_text = build_step_fragment_scaffold(
            target="workflow.step.state_set",
            snippet='- name: remember-profile\n  state_set:\n    state.shared_state["active_profile"]: review',
        )

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:state-set-step-fragment")

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_step_fragment_scaffold_validates_for_step_if_target(self) -> None:
        workflow_text = build_step_fragment_scaffold(
            target="workflow.step.if",
            snippet='- name: Add close comment\n  if: is_present(inputs.close_comment)\n  uses: gh.issue.comment.add\n  with:\n    repository: inputs.repository\n    issue_number: inputs.issue_number\n    body: inputs.close_comment',
        )

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:step-if-fragment")

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_workflow_fragment_scaffold_validates_for_workflow_profile_target(self) -> None:
        workflow_text = build_workflow_fragment_scaffold(
            target="workflow.profile",
            snippet='version: 0\nworkflow: inspect-issue\nprofile: backend-default\ninputs:\n  repository: {}\nblocks:\n  - guards:\n      - inputs.repository == "acme/backend"\n  - steps:\n      - name: remember\n        value: "ok"',
        )

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:workflow-profile")

        self.assertEqual(report.status, RuntimeStatus.OK)


if __name__ == "__main__":
    unittest.main()
