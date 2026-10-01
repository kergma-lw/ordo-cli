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
        self.assertIn(
            "declares the activation inputs a workflow accepts, requires, or gives defaults",
            result.stdout,
        )

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

    def test_input_authoring_guidance_and_examples_are_discoverable(self) -> None:
        for handle in ("workflow.inputs", "workflow.inputs_contract", "playbook.workflows.with"):
            with self.subTest(handle=handle):
                result = self.run_help("describe", handle)
                json_result = self.run_help("describe", handle, "--json")
                self.assertEqual(result.returncode, 0)
                self.assertEqual(json_result.returncode, 0)
                self.assertIn("use when:", result.stdout)
                self.assertIn("do not use for:", result.stdout)
                self.assertIn("inspect next:", result.stdout)
                self.assertIn("canonical examples:", result.stdout)
                payload = json.loads(json_result.stdout)
                self.assertEqual(payload["snippet_coverage"], "excerpt_verified")
                self.assertTrue(payload["canonical_examples"])
                if handle == "playbook.workflows.with":
                    for text in (
                        "required and optional caller placeholders",
                        "Expose each declared input",
                        "caller must provide through `key:`",
                        "caller may provide it",
                        "null, false, or zero",
                        "playbook_required_and_optional_caller_inputs",
                        "active_profile_key:",
                        "repo_dir?:",
                    ):
                        self.assertIn(text, result.stdout)
                else:
                    texts = (
                        "Document required and optional root inputs",
                        "description:",
                        "required: false",
                    ) if handle == "workflow.inputs" else (
                        "A required input and an explicitly optional input",
                        "description:",
                        "required: false",
                    )
                    for text in texts:
                        self.assertIn(text, result.stdout)

    def test_features_and_launch_help_publish_input_authoring_boundary(self) -> None:
        for args in (("features",), ("command-line",), ("describe", "command-line.ordo-playbook")):
            with self.subTest(args=args):
                result = self.run_help(*args)
                self.assertEqual(result.returncode, 0)
                if args == ("features",):
                    self.assertIn("Workflow-authoring feature map", result.stdout)
                    continue
                if args == ("command-line",):
                    self.assertIn("supplies or replaces one input", result.stdout)
                    self.assertNotIn("input_authoring", result.stdout)
                    continue
                self.assertIn("Command-line reference", result.stdout)
                self.assertIn("public flags:", result.stdout)
                self.assertIn("supplies or replaces one input", result.stdout)

    def test_search_hides_internal_input_advisory_codes(self) -> None:
        for code, handle in (
            ("review.workflow.input_description_missing", "workflow.inputs"),
            ("review.playbook.input_caller_slot_missing", "playbook.workflows.with"),
        ):
            with self.subTest(code=code):
                result = self.run_help("search", code)
                self.assertEqual(result.returncode, 0)
                self.assertNotIn(handle, result.stdout)
                self.assertIn("No topic, fact, or operation matches found.", result.stdout)
