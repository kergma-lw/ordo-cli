"""Practical graph help and its exact verified output example."""

import pytest
import yaml

from ordo.cli import GRAPH_MODE_HELP
from ordo.help_cli import _append_text_canonical_examples
from ordo.model.help_snippets import describe_help_snippets
from ordo.runtime.graphing import render_static_graph
from ordo.runtime.help_snippet_runner import verify_help_snippet


def test_graph_mode_help_answers_practical_questions():
    for text in ("Show how workflows connect through persistent state.",
                 "No active task is required", "+field", "−field", "?", "↔",
                 "Shared context: writers → readers, not execution order.",
                 "(data use; alternative sources)", "not a mandatory sequence",
                 "alternative ends are not sequential steps", "when their relationships leave a choice",
                 "matching context instance", "does not read saved state",
                 "independence in external systems", "workflows show <workflow>",
                 "check <workflow>", "explain <workflow>",
                 "ordo-playbook --profile backend graph", "ordo-playbook graph --json"):
        assert text in GRAPH_MODE_HELP
    for internal in ("schema_version", "next-shaped", "bootstrap", "source-aware", "32", "C/S"):
        assert internal not in GRAPH_MODE_HELP
    for text in ("Writers and deletions can also be branches", "also reads from: name",
                 "reads from: name?", "Fallback reads still count as data use"):
        assert text in GRAPH_MODE_HELP
    assert "↔ (reference) leaves" in GRAPH_MODE_HELP
    assert "without repeating its subtree" in GRAPH_MODE_HELP


def test_cli_example_displays_exact_verified_output_without_fixture_dump():
    registry = describe_help_snippets()
    examples = registry["command-line.ordo-playbook"]["canonical_examples"]
    assert len(examples) == 1
    example = examples[0]
    result = verify_help_snippet(snippet=example["yaml"], world="default",
                                 insertion_mode="graph_bundle", target="command-line.ordo-playbook")
    expected = yaml.safe_load(example["yaml"])["expected_text"].rstrip("\n")
    assert render_static_graph(result.graph_result) == expected
    lines = []
    _append_text_canonical_examples(lines, examples)
    text = "\n".join(lines)
    assert "verified graph output:" in text
    assert "\n".join(f"    {line}" for line in expected.splitlines()) in text
    assert "expected_links:" not in text
    assert "state_needs:" not in text
    # The diagram is verified by the existing scaffold, not a decorative label.
    with pytest.raises(ValueError, match="compact text mismatch"):
        verify_help_snippet(snippet=example["yaml"].replace("  remember (+item)", "  invented (+item)"),
                            world="default", insertion_mode="graph_bundle", target="command-line.ordo-playbook")
    technical = registry["state"]["canonical_examples"]
    assert {e["name"] for e in technical} >= {
        "static_graph_bridge_and_reset", "state_family_parameter_correspondence",
        "alternatives_do_not_select_a_parent", "state_mutation_roles_keep_one_workflow"}


def test_state_reference_example_verifies_same_operation_and_exact_output():
    examples = describe_help_snippets()["state"]["canonical_examples"]
    example = next(e for e in examples if e["name"] == "read_a_state_graph")
    result = verify_help_snippet(snippet=example["yaml"], world="default",
                                 insertion_mode="graph_bundle", target="state")
    forest = result.graph_result["summary"]["contours"][0]["role_view"]["forest"]
    inspect = next(node for node in forest["nodes"] if node["workflow"] == "inspect")
    sightings = [row for row in forest["display_rows"] if row["node"] == inspect["id"]]
    assert len(sightings) == 2
    assert sum(row["reference"] for row in sightings) == 1
    assert next(row for row in sightings if row["reference"])["conditional"]
