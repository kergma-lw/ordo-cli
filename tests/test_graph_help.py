"""Practical graph help and its exact verified output example."""

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


def test_command_line_help_does_not_teach_graph_mechanics():
    registry = describe_help_snippets()
    examples = registry["command-line.ordo-playbook"]["canonical_examples"]
    assert examples == []
    lines = []
    _append_text_canonical_examples(lines, examples)
    text = "\n".join(lines)
    assert "canonical examples:" not in text
    assert {e["name"] for e in registry["state"]["canonical_examples"]} == {
        "fixed_shared_state_key", "dynamic_shared_state_key", "state_read_before_write"}


def test_state_reference_example_verifies_same_operation_and_exact_output():
    from ordo.model.help_snippets import GRAPH_READING_EXAMPLE

    result = verify_help_snippet(snippet=GRAPH_READING_EXAMPLE["yaml"], world="default",
                                  insertion_mode="graph_bundle", target="state")
    forest = result.graph_result["summary"]["contours"][0]["role_view"]["forest"]
    inspect = next(node for node in forest["nodes"] if node["workflow"] == "inspect")
    sightings = [row for row in forest["display_rows"] if row["node"] == inspect["id"]]
    assert len(sightings) == 2
    assert sum(row["reference"] for row in sightings) == 1
    assert next(row for row in sightings if row["reference"])["conditional"]
