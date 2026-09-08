import os
import stat
import subprocess
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from ordo.runtime.help_snippet_runner import verify_help_snippet


class HelpSnippetRunnerTest(unittest.TestCase):
    def test_routine_bundle_uses_owner_only_executable_permissions(self) -> None:
        roots = []

        def fake_run(argv, *, cwd, capture_output, text, check):
            root = Path(cwd)
            roots.append(root)
            script = root / ".ordo/scripts/sample.py"
            self.assertEqual(Path(argv[0]).resolve(), script.resolve())
            for path in (root, script):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
                self.assertEqual(path.stat().st_uid, os.geteuid())
                self.assertTrue(os.access(path, os.X_OK))
            self.assertEqual(script.parent.parent.parent, root)
            self.assertTrue((root / ".ordo/routines.yaml").is_file())
            return subprocess.CompletedProcess(argv, 0, stdout='{"sample": "ok"}', stderr="")

        try:
            with patch("ordo.runtime.help_snippet_runner.subprocess.run", side_effect=fake_run) as run:
                result = verify_help_snippet(
                    snippet=textwrap.dedent('''\
                        routine_id: sample
                        registry_entry:
                          kind: probe
                          summary: Return sample data.
                          implementation:
                            argv: [".ordo/scripts/sample.py"]
                          outputs:
                            mode: data
                          failure_modes: [helper_failed]
                        implementation_path: .ordo/scripts/sample.py
                        implementation_text: |
                          #!/usr/bin/env python3
                          print('{"sample": "ok"}')
                        expected_stdout_json:
                          sample: ok
                        '''),
                    world="default", insertion_mode="routine_bundle", target="routine",
                )
            run.assert_called_once()
            self.assertEqual(result.status, "ok")
        finally:
            for root in roots:
                self.assertFalse(root.exists())

    def test_state_bundle_checks_real_bound_identity_without_execution(self) -> None:
        from ordo.model.help_snippets import STATE_BUNDLE_EXAMPLES

        for example in STATE_BUNDLE_EXAMPLES:
            with self.subTest(example=example["name"]), patch(
                "subprocess.run", side_effect=AssertionError("unexpected external execution")
            ), patch(
                "ordo.runtime.local_expression_engine.core.read_state_document",
                side_effect=AssertionError("unexpected state-content observation"),
            ):
                result = verify_help_snippet(
                    snippet=example["yaml"], world="default", insertion_mode="state_bundle", target="state",
                )
            self.assertEqual(result.status, example["verification"]["expected_status"])

    def test_state_bundle_distinct_files_do_not_alias(self) -> None:
        from ordo.model.help_snippets import STATE_BUNDLE_EXAMPLES

        snippet = STATE_BUNDLE_EXAMPLES[1]["yaml"].replace("alias: shared_state", "alias: common_state").replace(
            "expected_diagnostic_codes:\n  - validation.workflow.state_storage.write_before_last_read",
            "expected_diagnostic_codes: []",
        )
        result = verify_help_snippet(snippet=snippet, world="default", insertion_mode="state_bundle", target="state")
        self.assertEqual(result.status, "ok")

    def test_state_bundle_rejects_wrong_diagnostic_expectation(self) -> None:
        from ordo.model.help_snippets import STATE_BUNDLE_EXAMPLES

        with self.assertRaisesRegex(ValueError, "diagnostic mismatch"):
            verify_help_snippet(
                snippet=STATE_BUNDLE_EXAMPLES[1]["yaml"].replace("state_storage.write_before_last_read", "state_storage.identity_unresolved"),
                world="default", insertion_mode="state_bundle", target="state",
            )

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

    def test_runner_verifies_workflow_fragment_snippet_in_named_world(self) -> None:
        result = verify_help_snippet(
            snippet='version: 0\nworkflow: inspect-issue\nprofile: backend-default\ninputs:\n  repository: {}\nblocks:\n  - guards:\n      - inputs.repository == "acme/backend"\n  - steps:\n      - name: remember\n        value: "ok"',
            world="default",
            insertion_mode="workflow_fragment",
            target="workflow.profile",
        )

        self.assertEqual(result.status, "ok")
        self.assertIn("profile: backend-default", result.workflow_text)


if __name__ == "__main__":
    unittest.main()
