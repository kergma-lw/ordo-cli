"""Creation and connector-author SDK discovery contract, in text and JSON."""

import contextlib
import io
import json
from functools import lru_cache

import pytest

from ordo.help_cli import main


@lru_cache(maxsize=None)
def help_output(*args, as_json=False):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main([*args, *(["--json"] if as_json else [])]) == 0
    return json.loads(output.getvalue()) if as_json else output.getvalue()


@pytest.mark.parametrize("handle", ["connector.gh.pr.create", "connector.gh.pr.list", "connector.gh", "connector.gh.pr"])
def test_describe_readiness_definition_boundaries_neighbors_and_examples(handle):
    payload = help_output("describe", handle, as_json=True)
    text = help_output("describe", handle)
    metadata = payload["metadata"]
    human = payload["human"]
    for field in ("title", "goal", "summary"):
        assert human[field] in text
    assert not metadata["definition"].startswith("Do not")
    for field in ("use_when", "do_not_use_for", "nearest_surfaces"):
        assert metadata[field], (handle, field)
    assert human["sections"], handle
    for neighbor in metadata["nearest_surfaces"]:
        assert help_output("describe", neighbor["handle"], as_json=True)
    assert payload["snippet_coverage"] != "none", f"{handle} requires verified source examples"
    assert payload["canonical_examples"]
    if handle == "connector.gh.pr.create":
        assert any(example["form"] == "workflow_fragment" for example in payload["canonical_examples"])
    for example in payload["canonical_examples"]:
        assert example["verification"]
        source = example.get("yaml")
        assert source, "Example must render verified source"
    for example in payload["canonical_examples"]:
        assert example["name"] in text and example["summary"] in text
        source = example.get("yaml")
        assert source.strip() in text or all(line.strip() in text for line in source.splitlines())


@pytest.mark.parametrize("as_json", [False, True])
def test_create_describe_preserves_refusal_identity_and_uncertainty(as_json):
    result = help_output("describe", "connector.gh.pr.create", as_json=as_json)
    text = json.dumps(result) if as_json else result
    phrases = (
            "explicit boolean draft", "body defaults to empty", "repository is optional",
        "head_repository", "consistency assertion", "no fork guessing", "repository NAME",
        "same-branch/same-repository", "state: open", "complete traversal", "head_repository_key",
        "including draft", "already_exists", "pull_number", "no POST", "ambiguous", "precheck_failed",
        "one POST", "validated HTTP 201", "created=true", "created=false", "created=null",
        "creation_unknown", "HTTP 422", "create_refused", "preserve API errors",
        "No POST retry", "readback reconciliation", "not find-or-reuse", "state: all",
            "no atomic uniqueness", "exactly-once", "No CI waiting",
    ) if as_json else (
            "explicit draft value", "body is optional", "exact source repository", "does not guess forks",
            "matching open pull request", "refused rather than reused", "creation is confirmed",
            "outcome is unknown", "not blindly retried",
    )
    for phrase in phrases:
        assert phrase in text, phrase


@pytest.mark.parametrize("as_json", [False, True])
def test_connector_authoring_describe_explains_the_public_capability_boundary(as_json):
    result = help_output("describe", "connector.authoring", as_json=as_json)
    text = json.dumps(result) if as_json else result
    phrases = ("stable", "existing operations", "reader-facing", "No checked example")
    for phrase in phrases:
        assert phrase in text, phrase


@pytest.mark.parametrize("topic", ["features", "overview", "model", "workflow-rules", "capabilities", "operations"])
@pytest.mark.parametrize("as_json", [False, True])
def test_discovery_routes_to_creation_and_sdk_contracts(topic, as_json):
    result = help_output(topic, as_json=as_json)
    text = json.dumps(result) if as_json else result
    if not as_json and topic in {"features", "overview", "model", "workflow-rules", "capabilities"}:
        assert text
        return
    if topic == "operations":
        assert "gh.pr.create" in text
        return
    for phrase in ("gh.pr.create", "already_exists", "created=null", "connector.authoring"):
        assert phrase in text, (topic, phrase)
    assert "gh.pr.create is not implemented" not in text


@pytest.mark.parametrize("query,handle", [("outcome is unknown", "connector.gh.pr.create"), ("reader-facing guide", "connector.authoring")])
def test_search_routes_to_semantic_describe(query, handle):
    assert f"ordo-help describe {handle} --json" in json.dumps(help_output("search", query, as_json=True))
    assert handle in help_output("search", query)


def test_operation_catalog_preserves_creation_action_and_list_signature():
    action = help_output("operation", "gh.pr.create", as_json=True)["operation"]
    assert action["kind"] == "action"
    assert action["inputs"]["draft"] == "boolean"
    assert action["outputs"]["created"] == "boolean | null"
    assert {"already_exists", "ambiguous", "precheck_failed", "create_refused", "creation_unknown"} <= set(action["failure_modes"])
    probe = help_output("operation", "gh.pr.list", as_json=True)["operation"]
    assert probe["kind"] == "probe"
    assert set(probe["inputs"]) == {"repository", "head", "head_owner", "base", "state"}
