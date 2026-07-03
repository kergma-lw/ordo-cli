import unittest

from ordo.runtime import validate_workflow_text
from ordo.runtime.state_paths import parse_state_path


class RuntimeStatePathTest(unittest.TestCase):
    def test_parse_state_path_returns_stable_shape(self) -> None:
        parsed = parse_state_path("states.task_state[inputs.issue_ref].branch")

        self.assertEqual(parsed.state_name, "task_state")
        self.assertEqual(parsed.key_reference, ("inputs", "issue_ref"))
        self.assertEqual(parsed.fields, ("branch",))

    def test_parse_state_path_allows_nested_input_reference_and_field_chain(self) -> None:
        parsed = parse_state_path("states.task_state[inputs.issue.ref].branch.name")

        self.assertEqual(parsed.key_reference, ("inputs", "issue", "ref"))
        self.assertEqual(parsed.fields, ("branch", "name"))

    def test_validation_rejects_invalid_state_delete_path(self) -> None:
        report = validate_workflow_text(
            """
version: 0
workflow: open-task
guards: []
steps:
  - name: forget-branch
    state_delete: states.task_state[issue_ref].branch
"""
        )

        self.assertEqual(report.diagnostics[0].code, "validation.workflow.state_path.syntax")
        self.assertEqual(report.diagnostics[0].path, ("steps", "0", "state_delete"))

    def test_validation_rejects_multiple_state_set_targets(self) -> None:
        report = validate_workflow_text(
            """
version: 0
workflow: open-task
guards: []
steps:
  - name: remember-branch
    state_set:
      states.task_state[inputs.issue_ref].branch: ${inputs.branch}
      states.task_state[inputs.issue_ref].pr: ${inputs.pr}
"""
        )

        self.assertEqual(report.diagnostics[0].code, "validation.workflow.state_set.entry_count")


if __name__ == "__main__":
    unittest.main()
