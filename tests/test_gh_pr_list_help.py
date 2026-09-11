"""Public text/JSON discovery and nine-point describe coverage for PR listing."""

import contextlib
import io
import json
from functools import lru_cache

import pytest
import yaml

from ordo.help_cli import main


@lru_cache(maxsize=None)
def help_output(*args, as_json=False):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main([*args, *(["--json"] if as_json else [])]) == 0
    return json.loads(output.getvalue()) if as_json else output.getvalue()


@pytest.mark.parametrize("handle", ["connector.gh", "connector.gh.pr", "connector.gh.pr.list"])
def test_describe_nine_point_definition_boundaries_neighbors_and_examples(handle):
    """Points 1–3, 5–6, 8: definition, contrast, neighbors, real fragments, rendering."""
    payload = help_output("describe", handle, as_json=True)
    text = help_output("describe", handle)
    metadata = payload["metadata"]
    assert metadata["definition"] in text
    assert not metadata["definition"].startswith("Do not")
    for field in ("use_when", "do_not_use_for", "nearest_surfaces", "inspect_next"):
        assert metadata[field], (handle, field)
    assert "use when:" in text and "do not use for:" in text
    for neighbor in metadata["nearest_surfaces"]:
        assert neighbor["handle"] in text
    assert "connector.gh.pr.list" in text
    assert payload["snippet_coverage"] != "none"
    assert payload["canonical_examples"]
    assert any(example["form"] == "workflow_fragment" for example in payload["canonical_examples"])
    for example in payload["canonical_examples"]:
        assert example["verification"]
        assert example["name"] in text
        assert example["summary"] in text
        assert example.get("yaml")


@pytest.mark.parametrize("as_json", [False, True])
def test_list_describe_is_self_contained_and_explains_terms(as_json):
    """Points 4, 7–8: understandable identity, success scope, and decision boundaries."""
    result = help_output("describe", "connector.gh.pr.list", as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in (
        "repository argument is optional", "overrides the bootstrapped connector_contexts.gh.repository",
        "omitted or null uses that context", "Malformed explicit values fail without fallback",
        "no resolved repository is an error", "state is required: open|closed|all",
        "head repository owner (user or organization)", "not PR author", "requires head",
        "one owner can own multiple repositories", "exact fork matching",
        "repository identity is case-insensitive", "head_repository preserves API case",
        "nullable head_repository_key is the lowercase identity", "known nonnull key",
        "only(head_repository_key=inputs.head_repository | lower)", "unknown keys block",
        "subprocess.TimeoutExpired", "pull_list_unavailable with no partial outputs",
        "head_sha", "base_repository", "base_ref", "base_sha", "pull_ref", "draft",
        "known merge timestamp", "missing or indeterminate evidence derives null",
        "Never turn unknown into false", "100 pages of 100 items", "cannot publish partial success",
        "server head filter as owner:branch", "only state/base server filters", "exact head matching locally across all pages",
        "Missing head_ref when local filtering is required fails", "before local filtering",
        "GitHub.com only", "bootstrap authentication host", "/repositories/id/pulls",
        "validates repository IDs", "never follow response URLs directly",
        "state: open and nonnull merged_at is contradictory and fails",
        "no public page/cursor/limit", "not the search index", "not an atomic snapshot",
        "total remote count guarantee", "no matches within the supplied filters",
        "not automatically the correct PR", "Closed/merged history", "unknown facts block",
        "does not authorize creation, reopening, or merge",
        "gh.pr.create is a separate action with its own mandatory open check",
    ):
        assert phrase.lower() in text.lower(), phrase
    assert "gh.pr.create is not implemented" not in text


def test_canonical_list_fragments_teach_classification_and_unknown_boundary():
    payload = help_output("describe", "connector.gh.pr.list", as_json=True)
    examples = payload["canonical_examples"]
    assert {example["kind"] for example in examples} >= {"positive", "negative"}
    for example in examples:
        assert example["form"] == "workflow_fragment"
        workflow = yaml.safe_load(example["yaml"])
        steps = [step for block in workflow["blocks"] for step in block.get("steps", [])]
        listing = next(step for step in steps if step.get("uses") == "gh.pr.list")
        assert listing["with"]["state"] == "all"
        assert {"head", "head_owner", "base"} <= listing["with"].keys()
        assert not {"page", "cursor", "limit"} & listing["with"].keys()
        assert all(step.get("uses") not in {"gh.pr.create", "gh.pr.merge"} for step in steps)
        assert any("gate" in step for step in steps)
        for classification in ("no_pr", "exactly_one_open", "ambiguous_multiple_open", "only_closed_history"):
            assert classification in example["yaml"]
        assert "only(head_repository_key=inputs.head_repository | lower)" in example["yaml"]
        assert any(
            'only(head_repository_key!=null) | only(head_repository_key!="") | length | eq(step.candidates.outputs.count)'
            in condition
            for step in steps if "gate" in step
            for condition in step["gate"].get("all", [])
        )
        assert "merged=null" in example["yaml"]


@pytest.mark.parametrize("topic", ["features", "overview", "workflow-rules"])
@pytest.mark.parametrize("as_json", [False, True])
def test_list_guidance_aligns_with_authoring_bootstrap(topic, as_json):
    """Point 9: shared authoring guidance agrees with the describe examples."""
    result = help_output(topic, as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in ("gh.pr.list", "state: all", "head_owner", "one open", "multiple open", "closed history",
                   "unknown facts block", "gh.pr.create is a separate action with its own mandatory open check"):
        assert phrase in text, (topic, phrase)
    assert "gh.pr.create is not implemented" not in text


def test_operation_and_describe_discover_input_fields_and_minimal_items():
    operation = help_output("operation", "gh.pr.list", as_json=True)["operation"]
    metadata = help_output("describe", "connector.gh.pr.list", as_json=True)["metadata"]
    text = help_output("operation", "gh.pr.list")
    expected = {"repository", "head", "head_owner", "base", "state"}
    assert operation["kind"] == "probe"
    assert set(operation["inputs"]) == expected
    assert metadata["inputs"] == operation["inputs"]
    for name in expected:
        assert name in text
    assert set(operation["outputs"]["items"][0]) == {
        "number", "url", "state", "draft", "merged", "merged_at", "head_repository", "head_repository_key", "head_owner",
        "head_ref", "head_sha", "base_repository", "base_ref", "base_sha", "pull_ref",
    }


@pytest.mark.parametrize("query", ["gh.pr.list", "head_owner", "closed history"])
def test_search_routes_operation_and_input_terms_to_list_describe(query):
    payload = help_output("search", query, as_json=True)
    text = help_output("search", query)
    assert "ordo-help describe connector.gh.pr.list --json" in json.dumps(payload)
    assert "connector.gh.pr.list" in text
