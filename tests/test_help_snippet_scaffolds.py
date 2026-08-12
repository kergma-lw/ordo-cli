import unittest

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import validate_workflow_text
from ordo.runtime.help_snippet_scaffolds import (
    INSERTION_CONTRACTS,
    build_expression_value_scaffold,
    build_step_field_scaffold,
)


class HelpSnippetScaffoldTest(unittest.TestCase):
    def test_insertion_contracts_publish_supported_targets(self) -> None:
        self.assertEqual(set(INSERTION_CONTRACTS.keys()), {"expression_value", "step_field"})
        self.assertIn("workflow.step.if", INSERTION_CONTRACTS["step_field"].supported_targets)
        self.assertIn("state", INSERTION_CONTRACTS["expression_value"].supported_targets)

    def test_expression_value_scaffold_validates_for_state_target(self) -> None:
        workflow_text = build_expression_value_scaffold(target="state", snippet='state.shared_state["active_profile"]')

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:state")

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_expression_value_scaffold_validates_for_lookup_target(self) -> None:
        workflow_text = build_expression_value_scaffold(target="workflow.local_expression.filter.lookup", snippet='inputs.status_labels | lookup("ready")')

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:lookup")

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_step_field_scaffold_validates_for_step_if_target(self) -> None:
        workflow_text = build_step_field_scaffold(target="workflow.step.if", snippet='state.shared_state["active_profile"] == "review"')

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:step-if")

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_step_field_scaffold_validates_for_state_set_target(self) -> None:
        workflow_text = build_step_field_scaffold(target="workflow.step.state_set", snippet='state_set:\n  state.shared_state["active_profile"]: review')

        report = validate_workflow_text(workflow_text, source="snippet-scaffold:state-set")

        self.assertEqual(report.status, RuntimeStatus.OK)


if __name__ == "__main__":
    unittest.main()
