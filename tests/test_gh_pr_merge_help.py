"""Public text/JSON readiness checks for the asynchronous PR merge help family."""

import contextlib
import io
import json

import pytest

from ordo.help_cli import main


HANDLES = (
    "connector.gh",
    "connector.gh.pr",
    "connector.gh.pr.checks",
    "connector.gh.pr.merge",
    "connector.gh.pr.merge.request",
)


def help_output(*args, as_json=False):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main([*args, *(["--json"] if as_json else [])]) == 0
    return json.loads(output.getvalue()) if as_json else output.getvalue()


@pytest.mark.parametrize("handle", HANDLES)
def test_describe_readiness_definition_boundaries_neighbors_and_verified_examples(handle):
    """Exercise the published renderer as well as the machine-readable checklist."""
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
    assert payload["snippet_coverage"] != "none"
    examples = payload["canonical_examples"]
    assert examples
    assert any(example["form"] == "workflow_fragment" for example in examples)
    for example in examples:
        assert example["verification"]
        assert example["name"] in text
        assert example["summary"] in text
        assert example.get("yaml"), "Canonical examples must render verified source, not decorative prose"


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("handle,phrases", [
    ("connector.gh", ("expected_head_sha", "accepted CI head", "standalone/stacked/unknown", "no atomic base or stack guarantee", "request_id", "read-only probes and effectful actions", "not a read-only recipe")),
    ("connector.gh.pr", ("head_sha", "base_sha", "test_merge_state=verified", "parents B then H", "stack_state", "unknown scope", "freshly fetched head")),
    ("connector.gh.pr.checks", ("target=test_merge", "commit_sha", "statuses_complete", "check_runs_complete", "sha_evidence", "skipped", "neutral", "unknown", "empty", "trusted producers", "CI worker checkout", "expected H, not M")),
    ("connector.gh.pr.merge", ("accepted CI head", "expected_head_sha=H, not M", "rejects stacked PRs and unknown scope before submission", "request_compatibility=exact", "merge_method", "direct_merge", "request_id UUID", "not completion", "No atomic base or stack guarantee", "No polling", "admin bypass", "automatic issue closing", "not a structured reason code", "merge_refused (HTTP 400 refusal)", "merge_api_failed", "403/404/422", "HTTP 409 denotes an existing request", "merge_result_unknown")),
    ("connector.gh.pr.merge.request", ("pending", "merged", "failed", "enqueued", "24 hours", "404", "not proof that the merge failed", "successful probe observation", "not a structured reason code", "No polling", "merged=false alone cannot distinguish")),
])
def test_describe_preserves_merge_identity_status_and_scope_semantics(handle, phrases, as_json):
    result = help_output("describe", handle, as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in phrases:
        assert phrase in text, (handle, phrase)


@pytest.mark.parametrize("topic", ["features", "overview", "model", "workflow-rules", "capabilities", "operations"])
@pytest.mark.parametrize("as_json", [False, True])
def test_bootstrap_topics_discover_safe_async_merge(topic, as_json):
    result = help_output(topic, as_json=as_json)
    text = json.dumps(result) if as_json else result
    for phrase in ("gh.pr.checks", "gh.pr.merge", "gh.pr.merge.request", "expected_head_sha", "accepted CI head", "request_id", "not completion", "stacked", "unknown scope"):
        assert phrase in text, (topic, phrase)


@pytest.mark.parametrize("query,handle", [
    ("async merge", "connector.gh.pr.merge"),
    ("expected_head_sha", "connector.gh.pr.checks"),
    ("stack_state", "connector.gh.pr"),
    ("request_id", "connector.gh.pr.merge.request"),
    ("unavailable", "connector.gh.pr.merge.request"),
])
def test_search_routes_to_semantic_describes(query, handle):
    payload = help_output("search", query, as_json=True)
    text = help_output("search", query)
    assert f"ordo-help describe {handle} --json" in json.dumps(payload)
    assert handle in text


def test_merge_operation_catalog_preserves_action_probe_split():
    action = help_output("operation", "gh.pr.merge", as_json=True)["operation"]
    probe = help_output("operation", "gh.pr.merge.request", as_json=True)["operation"]
    assert action["kind"] == "action"
    assert probe["kind"] == "probe"
    assert action["inputs"]["expected_head_sha"] == "string"
    assert action["outputs"]["request_id"] == "string"
    assert probe["inputs"]["request_id"] == "string"
    assert "request_unavailable" in probe["failure_modes"]


@pytest.mark.parametrize("handle", ["connector.gh.pr.merge", "connector.gh.pr.merge.request"])
def test_describe_optional_repository_resolution(handle):
    payload = help_output("describe", handle, as_json=True)
    text = help_output("describe", handle)
    guidance = " ".join(payload["metadata"]["use_when"])
    for phrase in (
        "repository argument is optional",
        "overrides the bootstrapped connector_contexts.gh.repository",
        "omitted or null uses that context",
        "Malformed explicit values fail without fallback",
        "no resolved repository is an error",
        "workflow policy, not as an operation requirement",
    ):
        assert phrase in guidance
        assert phrase in text
    assert "Supply repository" not in guidance
    assert "Canonical examples require repository" not in text
    examples = {example["name"]: example for example in payload["canonical_examples"]}
    assert {"gh_pr_async_merge_head", "gh_pr_async_merge_test_merge", "gh_pr_async_merge_head_context"} <= examples.keys()
    context = examples["gh_pr_async_merge_head_context"]
    assert context["verification"]["world"] == "gh-pr-merge-head-context"
    assert context["name"] in text
    assert "# Supply via profile YAML: connectors: {gh: {repository: acme/mobile-app}}" in context["yaml"]
    assert "# Supply via profile YAML:" in text
    import yaml

    workflow = yaml.safe_load(context["yaml"])
    assert "connectors" not in workflow and "connector_contexts" not in workflow
    merge_steps = [step for block in workflow["blocks"] for step in block.get("steps", [])
                   if step.get("uses") in ("gh.pr.merge", "gh.pr.merge.request")]
    assert len(merge_steps) == 2
    assert all("repository" not in step["with"] for step in merge_steps)
    if handle.endswith(".request"):
        assert "resolved repository input/context and pull_number must match the saved request's target" in guidance


def test_shared_and_feature_guidance_preserves_optional_merge_repository():
    from ordo.help_cli import GH_PR_MERGE_GUIDANCE, build_features_response

    for guidance in (GH_PR_MERGE_GUIDANCE, json.dumps(build_features_response())):
        for phrase in (
            "repository is optional",
            "overrides the bootstrapped connector_contexts.gh.repository",
            "omitted or null uses that context",
            "Malformed explicit values fail without fallback",
            "no resolved repository is an error",
        ):
            assert phrase in guidance
