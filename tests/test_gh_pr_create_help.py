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


@pytest.mark.parametrize("handle", ["connector.gh.pr.create", "connector.authoring", "connector.gh.pr.list", "connector.gh", "connector.gh.pr"])
def test_describe_readiness_definition_boundaries_neighbors_and_examples(handle):
    payload = help_output("describe", handle, as_json=True)
    text = help_output("describe", handle)
    metadata = payload["metadata"]
    assert metadata["definition"] in text
    assert not metadata["definition"].startswith("Do not")
    for field in ("use_when", "do_not_use_for", "nearest_surfaces"):
        assert metadata[field], (handle, field)
    assert "use when:" in text and "do not use for:" in text
    for neighbor in metadata["nearest_surfaces"]:
        assert neighbor["handle"] in text
        assert help_output("describe", neighbor["handle"], as_json=True)
    assert payload["snippet_coverage"] != "none", f"{handle} requires verified source examples"
    assert payload["canonical_examples"]
    if handle == "connector.gh.pr.create":
        assert any(example["form"] == "workflow_fragment" for example in payload["canonical_examples"])
    for example in payload["canonical_examples"]:
        assert example["verification"]
        assert example["name"] in text and example["summary"] in text
        source = example.get("python") if example["form"] == "python_fragment" else example.get("yaml")
        assert source, "Example must render verified source"
        assert source.strip() in text or all(line.strip() in text for line in source.splitlines())
    if handle == "connector.authoring":
        example = payload["canonical_examples"][0]
        assert example["name"] == "sdk_same_family_probe_inputs"
        assert example["form"] == "python_fragment"
        assert example["verification"] == {
            "kind": "runner_verified", "world": "gh-sdk-probe-call",
            "insertion_mode": "sdk_probe_fragment", "target": handle, "expected_status": "ok",
        }
        assert "real family adapter and SDK context" in example["summary"]
        assert "not GitHub API behavior" in example["summary"]


@pytest.mark.parametrize("as_json", [False, True])
def test_create_describe_preserves_refusal_identity_and_uncertainty(as_json):
    result = help_output("describe", "connector.gh.pr.create", as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in (
        "explicit boolean draft", "body defaults to empty", "repository is optional",
        "head_repository", "consistency assertion", "no fork guessing", "repository NAME",
        "same-branch/same-repository", "state: open", "complete traversal", "head_repository_key",
        "including draft", "already_exists", "pull_number", "no POST", "ambiguous", "precheck_failed",
        "one POST", "validated HTTP 201", "created=true", "created=false", "created=null",
        "creation_unknown", "HTTP 422", "create_refused", "preserve API errors",
        "No POST retry", "readback reconciliation", "not find-or-reuse", "state: all",
        "no atomic uniqueness", "exactly-once", "No CI waiting",
    ):
        assert phrase in text, phrase


@pytest.mark.parametrize("as_json", [False, True])
def test_sdk_describe_publishes_resolved_probe_dependency_boundary(as_json):
    result = help_output("describe", "connector.authoring", as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in ("ctx.call", "inputs=None", "nonempty", "same-family probe", "already-resolved",
                   "gh.pr.list", "pr.list", "not reevaluated", "legacy", "Cross-family",
                   "probe-to-action hidden mutation", "no new action composition"):
        assert phrase in text, phrase


@pytest.mark.parametrize("topic", ["features", "overview", "model", "workflow-rules", "capabilities", "operations"])
@pytest.mark.parametrize("as_json", [False, True])
def test_discovery_routes_to_creation_and_sdk_contracts(topic, as_json):
    result = help_output(topic, as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in ("gh.pr.create", "already_exists", "created=null", "ctx.call", "same-family probe", "connector.authoring"):
        assert phrase in text, (topic, phrase)
    assert "gh.pr.create is not implemented" not in text


@pytest.mark.parametrize("query,handle", [("creation_unknown", "connector.gh.pr.create"), ("ctx.call", "connector.authoring")])
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
