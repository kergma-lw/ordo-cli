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
            snippet='state.shared_state["active_profile"] == "review"',
            world="default",
            insertion_mode="step_field",
            target="workflow.step.if",
        )

        self.assertEqual(result.status, "ok")
        self.assertIn('if: state.shared_state["active_profile"] == "review"', result.workflow_text)

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


if __name__ == "__main__":
    unittest.main()
