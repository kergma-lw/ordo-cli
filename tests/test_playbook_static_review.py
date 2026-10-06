import contextlib
import io
import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from ordo.cli import main as cli_main
from ordo.playbook import review_playbook_static


class PlaybookStaticReviewTest(unittest.TestCase):
    def _write_playbook(self, root: Path, *, workflows: str, files: dict[str, str]) -> None:
        directory = root / ".ordo" / "workflows"
        directory.mkdir(parents=True)
        (root / ".ordo" / "ordo.yaml").write_text(
            "version: 1\nworkflows:\n" + textwrap.indent(textwrap.dedent(workflows).strip(), "  ") + "\nstates: {}\n",
            encoding="utf-8",
        )
        for name, content in files.items():
            (directory / name).write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")

    def test_aggregates_clean_and_failing_workflows_without_runtime_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_playbook(
                root,
                workflows="""
                clean:
                  file: clean.yml
                  with:
                    value:
                failing:
                  file: failing.yml
                """,
                files={
                    "clean.yml": """
                    version: 0
                    workflow: clean
                    inputs:
                      value:
                        description: A supplied value
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
            with patch("ordo.runtime.reviewing.check_workflow") as check, patch("ordo.playbook.activate_playbook") as activate:
                result = review_playbook_static(playbook_path=root / ".ordo" / "ordo.yaml")

        check.assert_not_called()
        activate.assert_not_called()
        self.assertEqual(result["scope"], "playbook_static")
        self.assertTrue(result["contextual_checks_not_run"])
        self.assertEqual(result["review_status"], "needs_attention")
        self.assertEqual(result["finding_count"], 2)
        self.assertEqual(result["blocking_finding_count"], 2)
        self.assertEqual(result["advisory_finding_count"], 0)
        self.assertEqual({finding["severity"] for finding in result["results"][1]["findings"]}, {"blocking"})
        self.assertEqual([item["review_status"] for item in result["results"]], ["clean", "needs_attention"])

    def test_keeps_malformed_and_missing_entries_in_aggregate_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_playbook(
                root,
                workflows="""
                malformed: not-a-mapping
                missing:
                  file: missing.yml
                """,
                files={},
            )
            result = review_playbook_static(playbook_path=root / ".ordo" / "ordo.yaml")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["unavailable_workflow_count"], 2)
        self.assertEqual([item["review_status"] for item in result["results"]], ["unavailable", "unavailable"])
        self.assertEqual(result["results"][0]["diagnostics"][0]["code"], "playbook.workflow.entry_invalid")
        self.assertEqual(result["results"][1]["diagnostics"][0]["code"], "load.workflow.include.not_found")

    def test_checks_selected_profile_and_entry_binding_against_allowed_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_playbook(
                root,
                workflows="""
                sample:
                  file: sample.yml
                  with:
                    status: closed
                """,
                files={"sample.yml": """
                    version: 0
                    workflow: sample
                    inputs:
                      status:
                        allowed_values: [ready, queued]
                    blocks: [{steps: []}]
                """},
            )
            playbook = root / ".ordo" / "ordo.yaml"
            payload = playbook.read_text(encoding="utf-8")
            playbook.write_text(payload + "profiles:\n  selected:\n    file: selected.yml\ndefaults:\n  profile: selected\n", encoding="utf-8")
            (root / ".ordo" / "profiles").mkdir()
            (root / ".ordo" / "profiles" / "selected.yml").write_text("name: selected\ninputs:\n  status: invalid\n", encoding="utf-8")
            result = review_playbook_static(playbook_path=playbook)

        self.assertEqual(result["results"][0]["review_status"], "unavailable")
        self.assertEqual(
            [diagnostic["code"] for diagnostic in result["results"][0]["diagnostics"]],
            ["review.workflow.input_not_allowed", "review.workflow.input_not_allowed"],
        )

    def test_cli_review_without_workflow_returns_nonzero_for_blocking_findings(self) -> None:
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
                      value: {}
                    blocks: [{guards: []}, {steps: []}]
                    """,
                },
            )
            stdout = io.StringIO()
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch("sys.argv", ["ordo-playbook", "--json", "review"]), contextlib.redirect_stdout(stdout):
                    exit_code = cli_main()
            finally:
                os.chdir(previous)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["scope"], "playbook_static")
        self.assertEqual(payload["review_status"], "needs_attention")
        self.assertEqual(payload["blocking_finding_count"], 2)
        self.assertEqual(payload["advisory_finding_count"], 0)

    def test_cli_review_returns_zero_for_advisory_findings_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_playbook(
                root,
                workflows="""
                sample:
                  file: sample.yml
                  with:
                    body:
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
            stdout = io.StringIO()
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch("sys.argv", ["ordo-playbook", "--json", "review"]), contextlib.redirect_stdout(stdout):
                    exit_code = cli_main()
            finally:
                os.chdir(previous)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["blocking_finding_count"], 0)
        self.assertEqual(payload["advisory_finding_count"], 1)
        self.assertEqual(payload["pipe_style_advisory_count"], 1)
        self.assertEqual(payload["results"][0]["findings"][0]["severity"], "advisory")


if __name__ == "__main__":
    unittest.main()
