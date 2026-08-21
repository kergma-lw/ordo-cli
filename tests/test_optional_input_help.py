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
