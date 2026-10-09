import contextlib
import io
import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from ordo.agent_instructions import (
    AgentInstructionsError,
    BEGIN_MARKER,
    END_MARKER,
    render_agent_instructions,
    update_agent_instructions,
)
from ordo.cli import main as cli_main


class AgentInstructionsTest(unittest.TestCase):
    def _write_playbook(self, root: Path, *, workflows: str, files: dict[str, str]) -> Path:
        directory = root / ".ordo" / "workflows"
        directory.mkdir(parents=True)
        playbook = root / ".ordo" / "ordo.yaml"
        playbook.write_text(
            "version: 1\nworkflows:\n" + textwrap.indent(textwrap.dedent(workflows).strip(), "  ") + "\nstates: {}\n",
            encoding="utf-8",
        )
        for name, content in files.items():
            (directory / name).write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
        return playbook

    def _clean_playbook(self, root: Path) -> Path:
        return self._write_playbook(
            root,
            workflows="""
            inspect:
              file: inspect.yml
              category: Inspect
              description: Inspect the current item
              when: View the current item
              with:
                issue_number:
                verbose?:
            lifecycle:
              file: lifecycle.yml
              category: Lifecycle
              description: Advance the item
            """,
            files={
                "inspect.yml": """
                version: 0
                workflow: inspect
                inputs:
                  issue_number:
                    description: Issue number
                  verbose:
                    description: Include detail
                    required: false
                blocks: [{guards: []}, {steps: []}]
                """,
                "lifecycle.yml": """
                version: 0
                workflow: lifecycle
                inputs: {}
                blocks: [{guards: []}, {steps: []}]
                """,
            },
        )

    def test_render_uses_playbook_order_and_caller_slots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            playbook = self._clean_playbook(root)
            section, repository_root = render_agent_instructions(playbook_path=playbook)

        self.assertEqual(repository_root, root)
        self.assertLess(section.index("### Inspect"), section.index("### Lifecycle"))
        self.assertIn(
            "Inspect the current item → `ordo-playbook run inspect --input issue_number=<issue-number> [--input verbose=<verbose>]`",
            section,
        )
        self.assertIn("Advance the item → `ordo-playbook run lifecycle`", section)
        self.assertIn("### Operating rules", section)
        self.assertIn("Use `ordo-playbook workflows list` as the default discovery surface.", section)
        self.assertIn("can run probes and connector bootstrap commands", section)
        self.assertIn("without maintainer credentials when inspecting a foreign pull request", section)
        self.assertIn("Use a direct command or temporary legacy bypass only when the user explicitly asks for or approves it.", section)

    def test_render_uses_allowed_values_from_detailed_input_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            playbook = self._write_playbook(
                root,
                workflows="""
                update:
                  file: update.yml
                  description: Update one field
                  with:
                    priority:
                    confirm?:
                """,
                files={
                    "update.yml": """
                    version: 0
                    workflow: update
                    inputs:
                      priority:
                        description: Priority
                        allowed_values: [P0, P1, P2, P3]
                      confirm:
                        description: Confirmation
                        required: false
                        allowed_values: [FORCE_CLOSE]
                    blocks: [{guards: []}, {steps: []}]
                    """,
                },
            )
            section, _ = render_agent_instructions(playbook_path=playbook)

        self.assertIn(
            "Update one field → `ordo-playbook run update --input priority=<P0|P1|P2|P3> [--input confirm=<FORCE_CLOSE>]`",
            section,
        )

    def test_update_creates_replaces_and_preserves_text_outside_section(self) -> None:
        section = f"{BEGIN_MARKER}\nmanaged\n{END_MARKER}\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target, action = update_agent_instructions(section=section, repository_root=root)
            self.assertEqual(action, "created")
            self.assertEqual(target.read_text(encoding="utf-8"), section)

            original = f"before\n{BEGIN_MARKER}\nold\n{END_MARKER}\nafter\n"
            target.write_text(original, encoding="utf-8")
            _, action = update_agent_instructions(section=section, repository_root=root)
            self.assertEqual(action, "updated")
            self.assertEqual(target.read_text(encoding="utf-8"), f"before\n{section.rstrip()}\nafter\n")

    def test_update_adds_to_unmanaged_file_and_rejects_ambiguous_markers(self) -> None:
        section = f"{BEGIN_MARKER}\nmanaged\n{END_MARKER}\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "AGENTS.md"
            target.write_text("existing\n", encoding="utf-8")
            _, action = update_agent_instructions(section=section, repository_root=root)
            self.assertEqual(action, "added")
            self.assertEqual(target.read_text(encoding="utf-8"), f"existing\n\n{section}")

            target.write_text(f"{BEGIN_MARKER}\n{BEGIN_MARKER}\n{END_MARKER}\n", encoding="utf-8")
            with self.assertRaises(AgentInstructionsError):
                update_agent_instructions(section=section, repository_root=root)

    def test_preview_does_not_write_and_write_updates_after_clean_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._clean_playbook(root)
            stdout = io.StringIO()
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch("sys.argv", ["ordo-playbook", "agent-instructions"]), contextlib.redirect_stdout(stdout):
                    self.assertEqual(cli_main(), 0)
                self.assertFalse((root / "AGENTS.md").exists())
                written_stdout = io.StringIO()
                with patch("sys.argv", ["ordo-playbook", "agent-instructions", "--write"]), contextlib.redirect_stdout(written_stdout):
                    self.assertEqual(cli_main(), 0)
            finally:
                os.chdir(previous)

            rendered = stdout.getvalue()
            self.assertIn(BEGIN_MARKER, rendered)
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), rendered)
            written_payload = json.loads(written_stdout.getvalue())
            self.assertNotIn("section", written_payload)
            self.assertEqual(
                written_payload["next_step"],
                "Reload the agent to apply the updated instructions.",
            )

    def test_command_help_explains_preview_and_write_guard(self) -> None:
        stdout = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "agent-instructions", "--help"]), contextlib.redirect_stdout(stdout):
            self.assertEqual(cli_main(), 0)

        self.assertIn("reviews the whole playbook first", stdout.getvalue())
        self.assertIn("does not show or change AGENTS.md", stdout.getvalue())

    def test_command_rejects_workflow_execution_flags(self) -> None:
        with patch("sys.argv", ["ordo-playbook", "--input", "value=true", "agent-instructions"]):
            with self.assertRaises(SystemExit) as raised:
                cli_main()

        self.assertEqual(raised.exception.code, 2)

    def test_any_static_review_finding_blocks_preview_and_write_without_touching_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_playbook(
                root,
                workflows="""
                sample:
                  file: sample.yml
                """,
                files={
                    "sample.yml": """
                    version: 0
                    workflow: sample
                    inputs:
                      body:
                        description: Text that contains a Tasks section
                    blocks:
                      - guards: []
                      - steps:
                          - name: Extract tasks
                            value: '${markdown["Tasks"] with{root: inputs.body}}'
                            register: tasks
                    """,
                },
            )
            target = root / "AGENTS.md"
            target.write_text("unchanged\n", encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(root)
                for command in (["ordo-playbook", "--json", "agent-instructions"], ["ordo-playbook", "--json", "agent-instructions", "--write"]):
                    stdout = io.StringIO()
                    with patch("sys.argv", command), contextlib.redirect_stdout(stdout):
                        self.assertEqual(cli_main(), 1)
                    payload = json.loads(stdout.getvalue())
                    self.assertEqual(payload["status"], "blocked")
                    self.assertFalse(payload["written"])
                    self.assertNotIn("section", payload)
            finally:
                os.chdir(previous)

            self.assertEqual(target.read_text(encoding="utf-8"), "unchanged\n")

    def test_plain_blocked_output_lists_only_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_playbook(
                root,
                workflows="""
                clean:
                  file: clean.yml
                failing:
                  file: failing.yml
                """,
                files={
                    "clean.yml": """
                    version: 0
                    workflow: clean
                    inputs: {}
                    blocks: [{guards: []}, {steps: []}]
                    """,
                    "failing.yml": """
                    version: 0
                    workflow: failing
                    inputs:
                      value: {}
                    blocks: [{guards: []}, {steps: []}]
                    """,
                },
            )
            stdout = io.StringIO()
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch("sys.argv", ["ordo-playbook", "agent-instructions"]), contextlib.redirect_stdout(stdout):
                    self.assertEqual(cli_main(), 1)
            finally:
                os.chdir(previous)

        output = stdout.getvalue()
        self.assertIn("agent-instructions: blocked (2 findings: 2 blocking, 0 advisory)", output)
        self.assertIn("failing:inputs.value.description: blocking: Workflow input 'value' should declare a non-blank description", output)
        self.assertNotIn("review.workflow.input_description_missing", output)
        self.assertNotIn("clean:", output)


if __name__ == "__main__":
    unittest.main()
