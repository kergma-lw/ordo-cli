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
                blocks:
                  - guards:
                      - uses: git.worktree
                  - steps:
                      - name: inspect-issue
                        uses: gh.issue
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
                blocks:
                  - guards:
                      - git.branch != "main"
                  - steps: []
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
                blocks:
                  - guards:
                      - uses: git.worktree
                        expr: git.branch != "main"
                  - steps: []
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
                blocks:
                  - guards:
                      - ""
                  - steps: []
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
                blocks:
                  - guards:
                      - gh.issue(inputs.issue).status not in ["Done"]
                  - steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.guard_expr.syntax")
        self.assertEqual(report.diagnostics[0].path, ("blocks", "0", "guards", "0"))

    def test_guard_expression_requires_dotted_input_reference(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards:
                      - inputs == "repo#1"
                  - steps: []
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
                blocks:
                  - guards:
                      - inputs.issue(value="repo#1") == "repo#1"
                  - steps: []
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
                blocks:
                  - guards:
                      - gh.issue(repository=inputs.repository and inputs.other, issue_number=inputs.issue_number).status == "Open"
                  - steps: []
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
                blocks:
                  - guards:
                      - gh.issue(repository=inputs.repository, repository="repo#2", issue_number=inputs.issue_number).status == "Open"
                  - steps: []
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
                blocks:
                  - guards:
                      - gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state != "CLOSED"
                  - steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_valid_nested_project_issue_guard_expression_passes(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  repository: owner/repo
                  issue_number: 1
                  project_id: PVT_demo
                blocks:
                  - guards:
                      - gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id).exists
                  - steps: []
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
                blocks:
                  - guards: []
                  - steps: []
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
                blocks:
                  - guards:
                      - with: {}
                  - steps:
                      - uses: gh.issue
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
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        uses: gh.issue
                      - name: inspect
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.duplicate_name")

    def test_register_without_uses_fails(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: remember
                        register: issue
                        state_set:
                          state.memory[inputs.issue].value: ok
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.register_without_uses")

    def test_register_with_value_step_is_allowed(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: remember
                        value:
                          format: "{}/{}"
                          args:
                            - ${inputs.kind | lower}
                            - ${inputs.number}
                        register: branch
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_value_step_shape_accepts_runtime_value_surface(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: remember
                        value:
                          format: "{}"
                          args:
                            - ${inputs.kind | lower}
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_duplicate_register_names_fail(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        uses: gh.issue
                        register: issue
                      - name: comment
                        uses: gh.issue.comment
                        register: issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.duplicate_register")

    def test_invalid_register_shape_fails(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        uses: gh.issue
                        register: 7issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.register.pattern")

    def test_unknown_step_register_reference_fails(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: comment
                        uses: gh.issue.comment
                        with:
                          issue_id: ${step.issue.outputs.id}
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step_ref.unknown")

    def test_forward_step_register_reference_fails(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: comment
                        uses: gh.issue.comment
                        with:
                          issue_id: ${step.issue.outputs.id}
                      - name: inspect
                        uses: gh.issue
                        register: issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step_ref.forward")

    def test_later_step_block_can_read_earlier_registered_step(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        uses: gh.issue
                        register: issue
                  - guards: []
                  - steps:
                      - name: comment
                        uses: gh.issue.comment
                        with:
                          issue_id: ${step.issue.outputs.id}
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_duplicate_register_names_across_step_blocks_fail(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect-first
                        uses: gh.issue
                        register: issue
                  - guards: []
                  - steps:
                      - name: inspect-second
                        uses: gh.issue
                        register: issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.duplicate_register")

    def test_guard_expression_rejects_registered_step_reference(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards:
                      - step.issue.outputs.id == 1
                  - steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.guard_expr.step_ref")

    def test_invalid_value_expression_syntax_in_step_input_fails_validation(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        uses: gh.issue
                        with:
                          issue_ref: ${inputs.issue_ref |}
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.value_expr.syntax")

    def test_invalid_value_expression_syntax_in_state_set_value_fails_validation(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                state_needs:
                  task_memory: {}
                blocks:
                  - guards: []
                  - steps:
                      - name: remember
                        state_set:
                          state.task_memory[inputs.issue_ref].branch: ${format("unterminated)}
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.value_expr.syntax")

    def test_invalid_yaml_format_args_type_fails_validation(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        uses: gh.issue
                        with:
                          branch:
                            format: "{}/{}"
                            args: nope
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.value_expr.format.args_type")

    def test_invalid_yaml_format_args_type_in_value_step_fails_validation(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: remember
                        value:
                          format: "{}"
                          args: nope
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.value_expr.format.args_type")

    def test_step_if_must_use_expression_envelope(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if: inputs.enabled
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.if.expression")

    def test_step_if_rejects_yaml_boolean(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if: true
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.if.type")

    def test_step_if_and_register_cannot_be_used_together(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if: ${inputs.enabled}
                        uses: gh.issue
                        register: issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.if_with_register")

    def test_forward_step_register_reference_in_if_fails(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: comment
                        if: ${step.issue.outputs.open}
                        uses: gh.issue.comment
                      - name: inspect
                        uses: gh.issue
                        register: issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step_ref.forward")

    def test_step_if_rejects_statically_non_boolean_result(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if: ${format("hello")}
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.if_expr.result_type")

    def test_step_if_rejects_statically_non_boolean_not_input(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if: ${format("hello") | not}
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.if_expr.not_type")

    def test_step_if_accepts_boolean_composition(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  enabled: true
                  status: ok
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if: ${inputs.enabled and (inputs.status | eq("ok"))}
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_step_if_rejects_non_boolean_and_operand(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if: ${format("hello") and inputs.enabled}
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.if_expr.boolean_operand_type")

    def test_step_if_rejects_non_input_reference_root(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if: ${git.worktree.clean and inputs.enabled}
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.if_expr.root")

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
