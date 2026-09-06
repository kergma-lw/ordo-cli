import json
import os
import subprocess
import unittest
from pathlib import Path

from ordo.introspection import describe_playbook_contract


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "ordo-help"


class OptionalInputHelpTest(unittest.TestCase):
    def run_help(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(LAUNCHER), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )

    def test_playbook_contract_publishes_required_and_optional_caller_slot_forms(self) -> None:
        payload = describe_playbook_contract()
        with_field = next(item for item in payload["workflow_entry_fields"] if item["name"] == "with")

        self.assertEqual(with_field["caller_slot_forms"][0]["shape"], "key:")
        self.assertEqual(with_field["caller_slot_forms"][1]["shape"], "key?:")

    def test_help_describe_workflow_inputs_mentions_optional_and_defaulted_inputs(self) -> None:
        result = self.run_help("describe", "workflow.inputs")

        self.assertEqual(result.returncode, 0)
        self.assertIn("may require, treat as optional, or prefill with defaults", result.stdout)

    def test_help_describe_playbook_with_mentions_required_and_optional_caller_slots(self) -> None:
        result = self.run_help("describe", "playbook.workflows.with")
        json_result = self.run_help("describe", "playbook.workflows.with", "--json")

        self.assertEqual(result.returncode, 0)
        self.assertIn("key:", result.stdout)
        self.assertIn("key?:", result.stdout)
        self.assertEqual(json_result.returncode, 0)
        payload = json.loads(json_result.stdout)
        self.assertEqual(payload["metadata"]["caller_slot_forms"][0]["shape"], "key:")
        self.assertEqual(payload["metadata"]["caller_slot_forms"][1]["shape"], "key?:")

    def test_input_authoring_advisories_and_examples_are_discoverable(self) -> None:
        for handle in ("workflow.inputs", "workflow.inputs_contract", "playbook.workflows.with"):
            with self.subTest(handle=handle):
                result = self.run_help("describe", handle)
                json_result = self.run_help("describe", handle, "--json")
                self.assertEqual(result.returncode, 0)
                self.assertEqual(json_result.returncode, 0)
                self.assertIn("input_authoring", result.stdout)
                self.assertIn("unavailable", result.stdout)
                self.assertIn("check, plan, run, explain", result.stdout)
                self.assertIn("next", result.stdout)
                payload = json.loads(json_result.stdout)
                self.assertEqual(payload["snippet_coverage"], "excerpt_verified")
                self.assertTrue(payload["canonical_examples"])
                if handle == "playbook.workflows.with":
                    for text in (
                        "review.playbook.input_caller_slot_missing", "expose_caller_input",
                        "x: for required inputs", "x?: for optional inputs",
                        "CLI --input and --input-file overrides do not suppress it",
                        "only the selected launch profile counts", "null, false, or zero",
                        "active_profile_key:", "repo_dir?:",
                    ):
                        self.assertIn(text, result.stdout)
                else:
                    for text in (
                        "review.workflow.input_description_missing", "add_input_description",
                        "absent, null, empty, or whitespace-only", "description:", "required: false",
                    ):
                        self.assertIn(text, result.stdout)

    def test_features_and_launch_help_publish_input_authoring_boundary(self) -> None:
        for args in (("features",), ("command-line",), ("describe", "command-line.ordo-playbook")):
            with self.subTest(args=args):
                result = self.run_help(*args)
                self.assertEqual(result.returncode, 0)
                self.assertIn("input_authoring", result.stdout)
                self.assertIn("CLI overrides do not suppress", result.stdout)
                self.assertIn("activation errors", result.stdout)

    def test_search_finds_input_advisory_codes(self) -> None:
        for code, handle in (
            ("review.workflow.input_description_missing", "workflow.inputs"),
            ("review.playbook.input_caller_slot_missing", "playbook.workflows.with"),
        ):
            with self.subTest(code=code):
                result = self.run_help("search", code)
                self.assertEqual(result.returncode, 0)
                self.assertIn(handle, result.stdout)
