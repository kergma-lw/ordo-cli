import textwrap
import unittest

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import validate_profile_text, validate_workflow_text


class ValidationTest(unittest.TestCase):
    def test_valid_workflow_passes(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  issue: repo#1
                guards:
                  - uses: git.clean_worktree
                steps:
                  - name: inspect-issue
                    uses: gh.issue.view
                    with:
                      issue: repo#1
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.OK)
        self.assertEqual(report.diagnostics, ())

    def test_unknown_workflow_field_fails(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                notes: nope
                guards: []
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.unknown_field")
        self.assertEqual(report.diagnostics[0].path, ("notes",))

    def test_malformed_guard_and_step_fail_with_paths(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - with: {}
                steps:
                  - uses: gh.issue.view
                """
            )
        )

        codes = {diagnostic.code for diagnostic in report.diagnostics}
        self.assertIn("validation.uses.type", codes)
        self.assertIn("validation.name.type", codes)

    def test_duplicate_step_names_fail(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards: []
                steps:
                  - name: inspect
                    uses: gh.issue.view
                  - name: inspect
                    uses: gh.issue.view
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.duplicate_name")

    def test_profile_unknown_field_fails(self) -> None:
        report = validate_profile_text(
            textwrap.dedent(
                """
                name: backend-default
                surprise: true
                checks: []
                overrides: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].path, ("surprise",))

    def test_duplicate_override_targets_fail(self) -> None:
        report = validate_profile_text(
            textwrap.dedent(
                """
                name: backend-default
                overrides:
                  - target: shell.command
                  - target: shell.command
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.profile.override.duplicate_target")


if __name__ == "__main__":
    unittest.main()
