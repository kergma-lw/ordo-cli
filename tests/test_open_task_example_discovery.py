import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from ordo.help_cli import main as help_main
from ordo.model.help_snippets import describe_help_snippets, validate_help_snippet_registry
from ordo.runtime.help_snippet_scaffolds import INSERTION_CONTRACTS, build_workflow_fragment_scaffold
from tests import test_help_snippets as snippet_tests


@pytest.mark.parametrize("name", ["let-bindings", "set-active-task-from-gitx"])
def test_example_full_workflow_discovery_and_runner(name):
    handle = f"examples.{name}"
    registry = {handle: describe_help_snippets()[handle]}
    example = registry[handle]["canonical_examples"][0]
    source = (Path(__file__).resolve().parents[1] / f"examples/{name}.yaml").read_text(encoding="utf-8")
    assert example["yaml"] == source.rstrip("\n")
    assert example["source_excerpt"]["end_line"] == len(source.splitlines())
    assert registry[handle]["snippet_coverage"] == "runner_verified"
    assert example["verification"] == {
        "kind": "runner_verified", "world": "default", "insertion_mode": "workflow_fragment",
        "target": handle, "expected_status": "ok",
    }
    assert handle in INSERTION_CONTRACTS["workflow_fragment"].supported_targets
    assert build_workflow_fragment_scaffold(target=handle, snippet=example["yaml"]) == source
    validate_help_snippet_registry(registry)
    with patch("subprocess.run", side_effect=AssertionError("unexpected external execution")):
        with patch("tests.test_help_snippets.describe_help_snippets", return_value=registry):
            snippet_tests.HelpSnippetRegistryTest().test_runner_verified_snippets_validate_in_declared_worlds()
        for flags in ([], ["--json"]):
            with redirect_stdout(io.StringIO()) as output:
                assert help_main(["describe", handle, *flags]) == 0
            text = output.getvalue()
            if flags:
                payload = json.loads(text)
                assert payload["canonical_examples"] == [example]
                assert payload["snippet_coverage"] == "runner_verified"
                golden_dir = Path(__file__).resolve().parent / "golden"
                examples_golden = json.loads((golden_dir / "ordo_help_examples.json").read_text(encoding="utf-8"))
                assert next(row for row in examples_golden["examples"] if row["name"] == name) == payload["metadata"]
                root_golden = json.loads((golden_dir / "introspection_root.json").read_text(encoding="utf-8"))
                row = next(row for row in root_golden["sections"]["examples_catalog"]["examples"] if row["name"] == name)
                assert row == {key: payload["metadata"][key] for key in row}
            else:
                assert "\n".join(f"    {line}" for line in example["yaml"].splitlines()) in text
                assert "without execution" in text or "without Git/GitHub execution" in text
                if name == "set-active-task-from-gitx":
                    for boundary in ("not CSV", "missing type blocks", "missing status is allowed", "not rolled back", "explicit trusted code", "not the canonical .ordo workflow"):
                        assert boundary in text
                    assert "legacy shell fallback" not in text


def test_other_example_workflow_targets_remain_unsupported():
    with pytest.raises(ValueError, match="Unsupported workflow-fragment target"):
        build_workflow_fragment_scaffold(target="examples.minimal", snippet="version: 0\nblocks: []")
