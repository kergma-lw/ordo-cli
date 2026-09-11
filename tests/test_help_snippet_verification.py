import unittest
from pathlib import Path

from ordo.model.help_snippets import describe_help_snippets
from ordo.model.runtime import RuntimeStatus
from ordo.runtime import validate_workflow_text
from ordo.runtime.help_snippet_runner import verify_help_snippet


ROOT = Path(__file__).resolve().parents[1]


class HelpSnippetVerificationSuiteTest(unittest.TestCase):
    def test_all_published_help_snippets_verify_through_their_declared_path(self) -> None:
        registry = describe_help_snippets()

        for handle, entry in registry.items():
            for example in entry["canonical_examples"]:
                verification = example["verification"]
                kind = verification["kind"]
                if kind == "harness_verified":
                    workflow_text = _workflow_text_for_harness(verification["harness"], example["yaml"])
                    report = validate_workflow_text(workflow_text, source=f"snippet-suite:{handle}:{example['name']}")
                    self.assertEqual(report.status, RuntimeStatus.OK, f"{handle}:{example['name']}")
                    continue
                if kind == "excerpt_verified":
                    excerpt = example["source_excerpt"]
                    lines = (ROOT / excerpt["path"]).read_text(encoding="utf-8").splitlines()
                    expected = "\n".join(lines[excerpt["start_line"] - 1 : excerpt["end_line"]])
                    self.assertEqual(example["yaml"], expected, handle)
                    continue
                if kind == "runner_verified":
                    result = verify_help_snippet(
                        snippet=example["python"] if example["form"] == "python_fragment" else example["yaml"],
                        world=verification["world"],
                        insertion_mode=verification["insertion_mode"],
                        target=verification["target"],
                        overrides=verification.get("overrides"),
                    )
                    self.assertEqual(result.status, verification["expected_status"], f"{handle}:{example['name']}")
                    continue
                self.fail(f"Unsupported snippet verification kind: {kind}")


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
