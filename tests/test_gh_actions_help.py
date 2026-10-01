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
    "connector.gh.actions.run", "connector.gh.actions.run.jobs", "connector.gh",
])
def test_describe_definition_boundaries_neighbors_and_verified_examples(handle):
    payload = help_output("describe", handle, as_json=True)
    text = help_output("describe", handle)
    metadata = payload["metadata"]
    assert payload["human"]["goal"] in text
    assert not metadata["definition"].startswith("Do not")
    for field in ("use_when", "do_not_use_for", "nearest_surfaces"):
        assert metadata[field], (handle, field)
    for neighbor in metadata["nearest_surfaces"]:
        assert help_output("describe", neighbor["handle"], as_json=True)
    for section in payload["human"]["sections"]:
        for reference in section.get("references", []):
            assert reference["handle"] in text
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
        "directly associated Actions run", "found=false", "all other run fields null",
        "pull_requests", "workflow_path", "immutable event snapshot", "actions_run_unavailable",
    )),
    ("gh.actions.run.jobs", (
        "explicit positive integer attempt", "no latest-attempt default", "complete=true", "count=0",
        "100 pages", "stable total_count", "unique job IDs", "partial success", "check association",
        "actions_jobs_unavailable",
    )),
])
def test_describe_retains_inputs_outputs_failures_and_boundaries(reference, phrases, as_json):
    result = help_output("describe", f"connector.{reference}", as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in (*phrases, "optional and nullable", "workflow's GitHub repository context", "falling back",
                        "authenticated GitHub command-line session", "read-only", "non-atomic", "merge policy"):
        if not as_json and phrase.startswith("actions_"):
            continue
        assert phrase in text, (reference, phrase)


def test_checks_help_keeps_author_decisions_and_excludes_internal_mechanics():
    text = help_output("describe", "connector.gh.pr.checks")
    for phrase in (
        "source revision", "expected_head_sha", "trusted producers", "gh.pr.merge.expected_head_sha",
        "gh.actions.run", "gh.actions.run.jobs", "does not decide whether the checks passed", "gh_pr_checks_step",
    ):
        assert phrase in text
    for term in ("API", "GraphQL", "fixture", "SDK", "handler", "bootstrap", "check_suite_id", "check_run_id"):
        assert term not in text
    operation = help_output("operation", "gh.pr.checks", as_json=True)["operation"]
    assert operation["outputs"]["checks"][0]["check_suite_id"] == "integer"


def test_remaining_operation_guides_exclude_implementation_leaks_in_cli_and_site():
    from ordo.help_cli import build_operation_response
    from tools.build_help_site_docs import render_operation

    references = (
        "gh.repo.actions.permissions", "gh.actions.run", "gh.actions.run.jobs",
        "gh.pr", "gh.pr.checks", "git.branch.delete",
    )
    forbidden = ("api", "graphql", "worker", "tested-sha", "runner", "fixture", "synthetic test")
    for reference in references:
        payload = build_operation_response(reference)
        assert payload is not None
        for rendered in (help_output("describe", f"connector.{reference}"), render_operation("operations/example.md", payload)):
            lowered = rendered.lower()
            assert not any(term in lowered for term in forbidden), (reference, rendered)


@pytest.mark.parametrize("reference", ("gh.actions.run", "gh.actions.run.jobs"))
def test_actions_guides_describe_target_selection_and_observable_failures(reference):
    text = help_output("describe", f"connector.{reference}")

    for phrase in (
        "workflow's GitHub repository context",
        "provide a valid ASCII OWNER/REPO value to inspect another repository",
        "rejected rather than falling back",
        "result is unavailable",
    ):
        assert phrase in text
    for term in ("bootstrap", "connector_contexts", "diagnostic", "HTTP", "input_error"):
        assert term not in text


@pytest.mark.parametrize("as_json", [False, True])
def test_features_and_operations_route_to_real_operations(as_json):
    for topic in ("features", "operations"):
        result = help_output(topic, as_json=as_json)
        text = json.dumps(result) if as_json else result
        if topic == "features" and not as_json:
            assert "Workflow-authoring feature map" in text
        else:
            assert "actions.run" in text and "actions.run.jobs" in text
    features = help_output("features")
    assert "Workflow-authoring feature map" in features
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        assert main(["operation", "gh.actions", "--json"]) != 0


@pytest.mark.parametrize("query,handle", [
    ("check_suite_id", "connector.gh.actions.run"),
    ("check_run_id", "connector.gh.actions.run.jobs"),
    ("selected run cannot be read", "connector.gh.actions.run"),
    ("partial job lists", "connector.gh.actions.run.jobs"),
])
def test_search_routes_to_observation_contract(query, handle):
    assert handle in help_output("search", query)
    assert f"ordo-help describe {handle} --json" in json.dumps(help_output("search", query, as_json=True))
