import tempfile
import textwrap
import unittest
from pathlib import Path

from ordo.playbook import PlaybookError, activate_playbook, inspect_playbook_workflow


class PlaybookOptionalInputActivationTest(unittest.TestCase):
    def test_inspect_playbook_workflow_tracks_required_and_optional_caller_slots(self) -> None:
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
                          repository: owner/repo
                          issue_number:
                          close_comment?:
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository: {}\n  issue_number: {}\n  close_comment:\n    required: false\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            entry = inspect_playbook_workflow("inspect-issue", cwd=root)

        self.assertEqual(entry.with_, {"repository": "owner/repo"})
        self.assertEqual(entry.caller_inputs, ("issue_number",))
        self.assertEqual(entry.optional_caller_inputs, ("close_comment",))

    def test_activate_playbook_allows_optional_caller_slot_to_remain_missing(self) -> None:
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
                          repository: owner/repo
                          close_comment?:
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository: {}\n  close_comment:\n    required: false\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

        self.assertEqual(activated.workflow.inputs["repository"], "owner/repo")
        self.assertNotIn("close_comment", activated.workflow.inputs)
        self.assertEqual(activated.input_analysis.caller_optional_inputs, ("close_comment",))

    def test_activate_playbook_requires_required_caller_slot_even_when_workflow_input_is_optional(self) -> None:
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
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  issue_number:\n    required: false\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "playbook.workflow.input_missing")
        self.assertEqual(ctx.exception.diagnostics[0].details["missing_kind"], "caller_required_slot")

    def test_activate_playbook_requires_only_required_workflow_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                "version: 1\nworkflows:\n  inspect-issue:\n    file: inspect-issue.yml\nprofiles: {}\nstates: {}\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository:\n    required: true\n  close_comment:\n    required: false\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].details["missing_kind"], "workflow_required_input")
        self.assertEqual(ctx.exception.diagnostics[0].details["missing_inputs"], ["repository"])

    def test_activate_playbook_applies_defaulted_optional_workflow_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                "version: 1\nworkflows:\n  inspect-issue:\n    file: inspect-issue.yml\nprofiles: {}\nstates: {}\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository:\n    required: true\n  ship:\n    required: false\n    default: false\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            activated = activate_playbook(
                workflow_name="inspect-issue",
                input_overrides={"repository": "owner/repo"},
                cwd=root,
            )

        self.assertEqual(activated.workflow.inputs["repository"], "owner/repo")
        self.assertEqual(activated.workflow.inputs["ship"], False)
        self.assertEqual(activated.input_analysis.required_declared_inputs, ("repository",))
        self.assertEqual(activated.input_analysis.optional_declared_inputs, ("ship",))
