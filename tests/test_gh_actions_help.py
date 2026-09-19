"""Actions observation metadata, discoverability, and describe boundaries."""

import contextlib
import io
import json
from functools import lru_cache

import pytest

from connectors.gh.probes.actions.run import info as run_info
from connectors.gh.probes.actions.run.jobs import info as jobs_info
from ordo.help_cli import main


@lru_cache(maxsize=None)
def help_output(*args, as_json=False):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main([*args, *(["--json"] if as_json else [])]) == 0
    return json.loads(output.getvalue()) if as_json else output.getvalue()


@pytest.mark.parametrize("reference,info,inputs,failure", [
    ("gh.actions.run", run_info, {"repository", "run_id", "check_suite_id", "attempt"}, "actions_run_unavailable"),
    ("gh.actions.run.jobs", jobs_info, {"repository", "run_id", "attempt"}, "actions_jobs_unavailable"),
])
def test_operation_info_and_discovery_agree_on_observation_scope(reference, info, inputs, failure):
    operation = help_output("operation", reference, as_json=True)["operation"]
    declared = info()
    assert operation["kind"] == declared.kind == "probe"
    assert operation["effects"] == []
    assert operation["invalidates_observations"] == []
    assert operation["inputs"] == declared.inputs
    assert set(operation["inputs"]) == inputs
    assert operation["outputs"] == declared.outputs
    assert set(operation["failure_modes"]) == set(declared.failure_modes) == {"input_error", failure}
    assert "run_attempt" in operation["outputs"]
    assert "attempt" not in operation["outputs"]
    assert not {"tested_sha", "merge_allowed", "required_jobs", "logs"} & set(operation["outputs"])


@pytest.mark.parametrize("handle", [
    "connector.gh.actions.run", "connector.gh.actions.run.jobs", "connector.gh.pr.checks", "connector.gh",
])
def test_describe_definition_boundaries_neighbors_and_verified_examples(handle):
    payload = help_output("describe", handle, as_json=True)
    text = help_output("describe", handle)
    metadata = payload["metadata"]
    assert metadata["definition"] in text
    assert not metadata["definition"].startswith("Do not")
    for field in ("use_when", "do_not_use_for", "nearest_surfaces"):
        assert metadata[field], (handle, field)
    for neighbor in metadata["nearest_surfaces"]:
        assert neighbor["handle"] in text
        assert help_output("describe", neighbor["handle"], as_json=True)
    assert payload["snippet_coverage"] != "none", f"{handle}: concurrent verified examples required"
    examples = payload["canonical_examples"]
    assert any(example["form"] == "workflow_fragment" for example in examples)
    # Existing PR merge or project examples alone do not teach the new Actions bridge.
    assert any("gh.actions.run" in example.get("yaml", "") for example in examples)
    for example in examples:
        assert example["verification"]
        assert example["name"] in text and example["summary"] in text
        assert example.get("yaml")
        assert all(line.strip() in text for line in example["yaml"].splitlines())


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("reference,phrases", [
    ("gh.actions.run", (
        "exactly one", "omitted/null attempt", "latest observed run_attempt", "pinned numbered attempt",
        "CheckSuite.workflowRun", "backreference", "found=false", "HTTP 404", "all other run fields null",
        "pull_requests", "workflow_path", "immutable event snapshot", "actions_run_unavailable",
    )),
    ("gh.actions.run.jobs", (
        "explicit positive integer attempt", "no latest-attempt default", "complete=true", "count=0",
        "100 pages", "stable total_count", "unique job IDs", "partial success", "check_run_url",
        "https://api.github.com/repos/OWNER/REPO/check-runs/ID", "actions_jobs_unavailable",
    )),
])
def test_describe_retains_inputs_outputs_failures_and_boundaries(reference, phrases, as_json):
    result = help_output("describe", f"connector.{reference}", as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in (*phrases, "optional and nullable", "connector_contexts.gh.repository", "without fallback",
                   "input_error", "authenticated gh CLI", "bootstrap failures", "read-only",
                   "non-atomic", "tested-SHA", "worker checkout", "merge policy"):
        assert phrase in text, (reference, phrase)


@pytest.mark.parametrize("as_json", [False, True])
def test_checks_and_family_publish_nullable_suite_bridge(as_json):
    for handle in ("connector.gh.pr.checks", "connector.gh"):
        result = help_output("describe", handle, as_json=as_json)
        text = json.dumps(result) if as_json else result
        for phrase in ("check_suite_id", "nullable", "GraphQL", "found=false", "run_attempt",
                       "gh.actions.run.jobs", "check_run_id", "validated official API URL"):
            assert phrase in text, (handle, phrase)
    operation = help_output("operation", "gh.pr.checks", as_json=True)["operation"]
    assert operation["outputs"]["checks"][0]["check_suite_id"] == "integer"


@pytest.mark.parametrize("as_json", [False, True])
def test_features_and_operations_route_to_real_operations(as_json):
    for topic in ("features", "operations"):
        result = help_output(topic, as_json=as_json)
        text = json.dumps(result) if as_json else result
        assert "actions.run" in text and "actions.run.jobs" in text
    features = help_output("features")
    for phrase in ("check_suite_id", "run_attempt", "explicit attempt", "not an executable operation"):
        assert phrase in features
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        assert main(["operation", "gh.actions", "--json"]) != 0


@pytest.mark.parametrize("query,handle", [
    ("check_suite_id", "connector.gh.actions.run"),
    ("check_run_id", "connector.gh.actions.run.jobs"),
    ("actions_run_unavailable", "connector.gh.actions.run"),
    ("actions_jobs_unavailable", "connector.gh.actions.run.jobs"),
])
def test_search_routes_to_observation_contract(query, handle):
    assert handle in help_output("search", query)
    assert f"ordo-help describe {handle} --json" in json.dumps(help_output("search", query, as_json=True))
