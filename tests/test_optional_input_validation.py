import tempfile
import textwrap
import unittest
from pathlib import Path

from ordo.model.runtime import RuntimeStatus
from ordo.playbook import PlaybookError, inspect_playbook_workflow
from ordo.runtime import validate_workflow_text


class OptionalInputValidationTest(unittest.TestCase):
    def test_workflow_input_required_must_be_boolean(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: publish
                inputs:
                  priority:
                    required: sometimes
                blocks:
                  - steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.inputs.required.type")

    def test_workflow_input_required_true_conflicts_with_default(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: publish
                inputs:
                  priority:
                    required: true
                    default: high
                blocks:
                  - steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.inputs.required_default_conflict")

    def test_workflow_input_unknown_declaration_field_is_rejected(self) -> None:
        report = validate_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: publish
                inputs:
                  priority:
                    optional: true
                blocks:
                  - steps: []
                """
            )
        )

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.inputs.unknown_field")

    def test_allowed_values_must_be_unique_strings_and_include_the_default(self) -> None:
        cases = (
            ("allowed_values: []", "validation.workflow.inputs.allowed_values.empty"),
            ("allowed_values: [ready, 1]", "validation.workflow.inputs.allowed_values.item_type"),
            ("allowed_values: [ready, ready]", "validation.workflow.inputs.allowed_values.duplicate"),
            ("allowed_values: [ready]\ndefault: queued", "validation.workflow.inputs.allowed_values.default_membership"),
        )
        for declaration, expected_code in cases:
            with self.subTest(declaration=declaration):
                declaration = declaration.replace("\n", "\n                        ")
                report = validate_workflow_text(textwrap.dedent(f"""
                    version: 0
                    workflow: publish
                    inputs:
                      status:
                        {declaration}
                    blocks:
                      - steps: []
                """))
                self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
                self.assertIn(expected_code, {diagnostic.code for diagnostic in report.diagnostics})

    def test_playbook_rejects_optional_caller_slot_with_concrete_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        with:
                          close_comment?: hello
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  close_comment:\n    required: false\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                inspect_playbook_workflow("inspect-issue", cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "playbook.workflow.with_optional_slot_value_invalid")

    def test_playbook_accepts_required_and_optional_caller_slot_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        with:
                          issue_number:
                          close_comment?:
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  issue_number: {}\n  close_comment:\n    required: false\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            entry = inspect_playbook_workflow("inspect-issue", cwd=root)

        self.assertEqual(entry.caller_inputs, ("issue_number",))
        self.assertEqual(entry.optional_caller_inputs, ("close_comment",))
