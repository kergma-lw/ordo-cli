import contextlib
import io
import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from ordo.cli import main as cli_main


class OptionalInputModesTest(unittest.TestCase):
    def _run_cli(self, root: Path, *argv: str) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", *argv]):
            with patch("os.getcwd", return_value=str(root)):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = cli_main()
        payload = json.loads(stdout.getvalue()) if stdout.getvalue().strip() else {}
        return exit_code, payload, stderr.getvalue()

    def test_cli_modes_succeed_with_required_caller_slot_and_legacy_default_shorthand(self) -> None:
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
                          repository:
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      repository: {}
                      ship: false
                    blocks:
                      - guards:
                          - inputs.repository != ""
                      - steps:
                          - name: publish
                            publish:
                              repository: ${inputs.repository}
                              ship: ${inputs.ship}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            for mode in ("check", "review", "plan", "explain", "next", "run"):
                with self.subTest(mode=mode):
                    exit_code, payload, stderr = self._run_cli(root, "--input", "repository=owner/repo", "--json", mode, "inspect-issue")
                    self.assertEqual(exit_code, 0)
                    self.assertEqual(payload.get("mode", "run"), mode)
                    self.assertEqual(stderr, "")

    def test_cli_plan_allows_omitted_optional_caller_slot(self) -> None:
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
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      repository: {}
                      close_comment:
                        required: false
                    blocks:
                      - guards: []
                      - steps:
                          - name: publish
                            publish:
                              repository: ${inputs.repository}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            exit_code, payload, stderr = self._run_cli(root, "--json", "plan", "inspect-issue")

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["mode"], "plan")
        self.assertEqual(stderr, "")

    def test_cli_run_progress_steps_writes_progress_to_stderr_without_corrupting_json(self) -> None:
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
                          repository:
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      repository: {}
                    blocks:
                      - guards: []
                      - steps:
                          - name: publish
                            publish:
                              repository: ${inputs.repository}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            exit_code, payload, stderr = self._run_cli(root, "--input", "repository=owner/repo", "--progress-steps", "--json", "run", "inspect-issue")

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["published"], [{"repository": "owner/repo"}])
        self.assertEqual(stderr, "Running step: publish\n")

    def test_cli_rejects_progress_steps_outside_run_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "--progress-steps", "plan", "inspect-issue"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stderr(stderr):
                        with self.assertRaises(SystemExit) as ctx:
                            cli_main()

        self.assertNotEqual(ctx.exception.code, 0)
        self.assertIn("--progress-steps is only supported with run", stderr.getvalue())

    def test_cli_review_surfaces_optional_input_presence_guard_finding(self) -> None:
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
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      repository: {}
                      close_comment:
                        required: false
                    blocks:
                      - guards:
                          - inputs.repository != ""
                      - steps:
                          - name: publish
                            publish:
                              repository: ${inputs.repository}
                              close_comment: ${inputs.close_comment}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            exit_code, payload, stderr = self._run_cli(root, "--json", "review", "inspect-issue")

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["mode"], "review")
        self.assertEqual(stderr, "")
        finding_codes = {item["code"] for item in payload["outputs"]["findings"]}
        self.assertIn("review.workflow.optional_input_presence_guard_missing", finding_codes)

    def test_cli_plan_reports_missing_required_caller_slot(self) -> None:
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
                          repository:
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            exit_code, payload, stderr = self._run_cli(root, "--json", "plan", "inspect-issue")

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "resolution_error")
        self.assertEqual(payload["diagnostics"][0]["details"]["missing_kind"], "caller_required_slot")
        self.assertEqual(stderr, "")
