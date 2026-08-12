import unittest

from ordo.runtime.help_snippet_runner import verify_help_snippet


class HelpSnippetRunnerTest(unittest.TestCase):
    def test_runner_verifies_expression_value_snippet_in_named_world(self) -> None:
        result = verify_help_snippet(
            snippet='state.shared_state["active_profile"]',
            world="default",
            insertion_mode="expression_value",
            target="state",
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.world_name, "default")
        self.assertIn('sample: state.shared_state["active_profile"]', result.workflow_text)

    def test_runner_verifies_step_field_snippet_in_named_world(self) -> None:
        result = verify_help_snippet(
            snippet="is_present(inputs.close_comment)",
            world="default",
            insertion_mode="step_field",
            target="workflow.step.if",
        )

        self.assertEqual(result.status, "ok")
        self.assertIn("if: is_present(inputs.close_comment)", result.workflow_text)

    def test_runner_applies_world_overrides_deterministically(self) -> None:
        result = verify_help_snippet(
            snippet="inputs.repository",
            world="default",
            insertion_mode="expression_value",
            target="state",
            overrides={"inputs": {"repository": "acme/override"}},
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.effective_world["inputs"]["repository"], "acme/override")
        self.assertEqual(result.effective_world["inputs"]["project_id"], "PVT_demo")

    def test_runner_rejects_unknown_world(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown snippet world"):
            verify_help_snippet(
                snippet="inputs.repository",
                world="missing",
                insertion_mode="expression_value",
                target="state",
            )

    def test_runner_verifies_step_fragment_snippet_in_named_world(self) -> None:
        result = verify_help_snippet(
            snippet='- name: remember-profile\n  state_set:\n    state.shared_state["active_profile"]: review',
            world="default",
            insertion_mode="step_fragment",
            target="workflow.step.state_set",
        )

        self.assertEqual(result.status, "ok")
        self.assertIn('- name: remember-profile', result.workflow_text)

    def test_runner_verifies_step_if_fragment_snippet_in_named_world(self) -> None:
        result = verify_help_snippet(
            snippet='- name: Add close comment\n  if: is_present(inputs.close_comment)\n  uses: gh.issue.comment.add\n  with:\n    repository: inputs.repository\n    issue_number: inputs.issue_number\n    body: inputs.close_comment',
            world="default",
            insertion_mode="step_fragment",
            target="workflow.step.if",
        )

        self.assertEqual(result.status, "ok")
        self.assertIn("uses: gh.issue.comment.add", result.workflow_text)


if __name__ == "__main__":
    unittest.main()
