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

    def test_valid_expr_guard_workflow_passes(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - git.branch != "main"
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_object_guard_with_unknown_expr_field_fails(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - uses: git.clean_worktree
                    expr: git.branch != "main"
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.unknown_field")

    def test_guard_expression_must_not_be_empty(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - ""
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.guard_expr.empty")

    def test_guard_expression_syntax_error_is_reported(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - gh.issue(inputs.issue).status not in ["Done"]
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.guard_expr.syntax")
        self.assertEqual(report.diagnostics[0].path, ("guards", "0"))

    def test_guard_expression_requires_dotted_input_reference(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - inputs == "repo#1"
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.guard_expr.input_ref")

    def test_guard_expression_rejects_calling_inputs_like_probe(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - inputs.issue(value="repo#1") == "repo#1"
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.guard_expr.inputs_call")

    def test_guard_expression_rejects_non_value_argument_expression(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - gh.issue(issue=inputs.issue and inputs.other).status == "Open"
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.guard_expr.argument_value")

    def test_guard_expression_rejects_duplicate_argument_names(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - gh.issue(issue=inputs.issue, issue="repo#2").status == "Open"
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.guard_expr.duplicate_argument")

    def test_valid_guard_expression_with_named_argument_and_field_access_passes(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - gh.issue(issue=inputs.issue).status not in ["Done", "In review"]
                steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.OK)

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
