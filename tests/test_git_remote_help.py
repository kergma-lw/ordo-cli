"""Git remote observation schema, semantic discovery, and describe readiness."""

import contextlib
import io
import json
from functools import lru_cache

import pytest

from connectors.git.probes.remote import info
from ordo.help_cli import main


@lru_cache(maxsize=None)
def help_output(*args, as_json=False):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main([*args, *(["--json"] if as_json else [])]) == 0
    return json.loads(output.getvalue()) if as_json else output.getvalue()


def test_operation_schema_matches_probe_and_keeps_policy_out_of_outputs():
    operation = help_output("operation", "git.remote", as_json=True)["operation"]
    declared = info()
    assert operation["kind"] == declared.kind == "probe"
    assert operation["inputs"] == declared.inputs == {"remote": "string"}
    assert operation["outputs"] == declared.outputs == {
        "name": "string", "exists": "boolean", "fetch_urls": ["string"],
        "push_urls": ["string"], "mirror": "boolean | null",
    }
    assert set(operation["failure_modes"]) == set(declared.failure_modes) == {"probe_failed"}
    assert operation["effects"] == operation["invalidates_observations"] == []


@pytest.mark.parametrize("as_json", [False, True])
def test_describe_publishes_author_facing_observation_semantics(as_json):
    result = help_output("describe", "connector.git.remote", as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in (
        "`remote`: required", "team/origin", "exists=false", "fetch_urls",
        "push_urls", "mirror", "recorded destinations", "connector.git.repo", "connector.git.upstream",
        "connector.git.sync.push",
    ):
        assert phrase in text, phrase
    if not as_json:
        for phrase in ("get-url", "insteadOf", "exit 1", "probe.git_remote", "diagnostic", "runtime", "command evidence", "fixture", "live io"):
            assert phrase not in text, phrase


def test_describe_readiness_with_verified_fragment():
    handle = "connector.git.remote"
    payload = help_output("describe", handle, as_json=True)
    text = help_output("describe", handle)
    metadata = payload["metadata"]
    assert payload["human"]["summary"] in text
    assert payload["human"]["summary"].startswith("Observe")
    for field in ("use_when", "do_not_use_for", "nearest_surfaces"):
        assert metadata[field]
    assert {neighbor["handle"] for neighbor in metadata["nearest_surfaces"]} == {
        "connector.git.repo", "connector.git.upstream", "connector.git.sync.push",
    }
    for neighbor in metadata["nearest_surfaces"]:
        assert neighbor["handle"] in text
        assert help_output("describe", neighbor["handle"], as_json=True)
    assert payload["snippet_coverage"] != "none", "Concurrent verified snippet is required"
    examples = payload["canonical_examples"]
    assert any(example["form"] == "workflow_fragment" for example in examples)
    assert any("git.remote" in example.get("yaml", "") for example in examples)
    for example in examples:
        assert example["verification"]
        assert example["name"] in text and example["summary"] in text
        assert example.get("yaml")
        assert all(line.strip() in text for line in example["yaml"].splitlines())


@pytest.mark.parametrize("as_json", [False, True])
def test_features_teaches_real_primitive_and_domain_split(as_json):
    result = help_output("features", as_json=as_json)
    text = json.dumps(result) if as_json else result
    if not as_json:
        assert "Workflow-authoring feature map" in text
        return
    for handle in ("connector.git.remote", "connector.git.repo", "connector.git.upstream", "connector.git.sync.push"):
        assert handle in text
    for phrase in ("fetch_urls", "push_urls", "mirror=false", "exists=false", "mirror=null",
                   "literal observed URLs", "without normalization or redaction",
                   "caller chooses acceptable destinations"):
        assert phrase.lower() in text.lower()


@pytest.mark.parametrize("query", ["git.remote", "fetch_urls", "push_urls", "mirror"])
def test_search_routes_to_remote_semantic_contract(query):
    assert "git.remote" in help_output("search", query)
    assert "ordo-help operation git.remote --json" in json.dumps(help_output("search", query, as_json=True))
