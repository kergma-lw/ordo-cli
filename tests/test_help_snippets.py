import unittest
from pathlib import Path

from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.model.help_snippets import describe_help_snippets
from ordo.model.runtime import RuntimeStatus
from ordo.runtime import validate_workflow_text


ROOT = Path(__file__).resolve().parents[1]


class HelpSnippetRegistryTest(unittest.TestCase):
    def test_default_snippet_world_is_declared_with_explicit_fixture_buckets(self) -> None:
        worlds = describe_help_snippet_worlds()

        self.assertIn("default", worlds)
        default = worlds["default"]
        self.assertEqual(default["name"], "default")
        self.assertEqual(set(default.keys()), {"name", "summary", "inputs", "state", "probes", "actions"})
        self.assertIn("repository", default["inputs"])
        self.assertIn("shared_state", default["state"])
        self.assertIn("gh.issue", default["probes"])
        self.assertIn("gh.issue.comment.add", default["actions"])

    def test_harness_verified_snippets_validate_in_declared_hosts(self) -> None:
        registry = describe_help_snippets()

        for handle, entry in registry.items():
            for example in entry["canonical_examples"]:
                verification = example["verification"]
                if verification["kind"] != "harness_verified":
                    continue
                workflow_text = _workflow_text_for_harness(verification["harness"], example["yaml"])
                report = validate_workflow_text(workflow_text, source=f"snippet:{handle}:{example['name']}")
                self.assertEqual(report.status, RuntimeStatus.OK, f"{handle}:{example['name']}")

    def test_excerpt_verified_snippets_match_their_declared_source_lines(self) -> None:
        registry = describe_help_snippets()

        for handle, entry in registry.items():
            for example in entry["canonical_examples"]:
                verification = example["verification"]
                if verification["kind"] != "excerpt_verified":
                    continue
                excerpt = example["source_excerpt"]
                lines = (ROOT / excerpt["path"]).read_text(encoding="utf-8").splitlines()
                expected = "\n".join(lines[excerpt["start_line"] - 1 : excerpt["end_line"]])
                self.assertEqual(example["yaml"], expected, handle)


def _workflow_text_for_harness(harness: str, snippet: str) -> str:
    if harness == "state_expression_in_let":
        return f"""version: 0
workflow: snippet-state
state_needs:
  shared_state: {{}}
let:
  sample: {snippet}
blocks: []
"""
    if harness == "step_if_expression":
        return f"""version: 0
workflow: snippet-step-if
state_needs:
  shared_state: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    if: {snippet}
    value: true
"""
    if harness == "value_expression_lookup":
        return f"""version: 0
workflow: snippet-lookup
inputs:
  status_labels: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    value: {snippet}
"""
    if harness == "step_state_set_mapping":
        return f"""version: 0
workflow: snippet-state-set
state_needs:
  shared_state: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    {snippet.replace("\n", "\n    ")}
"""
    raise AssertionError(f"Unsupported harness: {harness}")


if __name__ == "__main__":
    unittest.main()
