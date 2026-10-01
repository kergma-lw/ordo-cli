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
    assert payload["human"]["goal"] in text
    assert not metadata["definition"].startswith("Do not")
    for field in ("use_when", "do_not_use_for", "nearest_surfaces"):
        assert metadata[field], (handle, field)
    assert "use when:" in text and "do not use for:" in text
    for neighbor in metadata["nearest_surfaces"]:
        assert help_output("describe", neighbor["handle"], as_json=True)
    for section in payload["human"]["sections"]:
        for reference in section.get("references", []):
            assert reference["handle"] in text
    assert payload["snippet_coverage"] != "none"
    examples = payload["canonical_examples"]
    assert examples
    assert any(example["form"] == "workflow_fragment" for example in examples) or handle == "connector.gh.pr.checks"
    for example in examples:
        assert example["verification"]
        assert example.get("yaml"), "Canonical examples must render verified source, not decorative prose"
    for example in examples:
        assert example["name"] in text
        assert example["summary"] in text


@pytest.mark.parametrize("handle,phrases", [
    ("connector.gh", ("GitHub context repository", "probe to observe facts", "action only when", "not permanent authorization", "or an atomic view")),
    ("connector.gh.pr", ("head_sha", "base_sha", "test_merge_state=verified", "parents B then H", "stack_state", "unknown scope", "freshly fetched head")),
    ("connector.gh.pr.checks", ("expected_head_sha", "commit_sha", "statuses_complete", "check_runs_complete", "skipped", "neutral", "unknown", "empty", "trusted producers", "individual jobs", "Do not substitute a later source revision")),
    ("connector.gh.pr.merge", ("workflow's GitHub repository context", "expected_head_sha", "standalone pull request with a known scope", "request_id", "not proof of completion", "already merged or queued", "unknown result", "inspect the saved request", "No atomic base or stack guarantee", "Waiting for completion")),
    ("connector.gh.pr.merge.request", ("pending", "merged", "failed", "enqueued", "24 hours", "expired or missing request ID", "not proof that the merge failed", "successful probe observation", "Polling, queue administration", "merged=false alone cannot distinguish")),
])
def test_describe_preserves_merge_identity_status_and_scope_semantics(handle, phrases):
    text = help_output("describe", handle)
    for phrase in phrases:
        assert phrase in text, (handle, phrase)


@pytest.mark.parametrize("topic", ["features", "overview", "model", "workflow-rules", "capabilities", "operations"])
@pytest.mark.parametrize("as_json", [False, True])
def test_bootstrap_topics_discover_safe_async_merge(topic, as_json):
    result = help_output(topic, as_json=as_json)
    text = json.dumps(result) if as_json else result
    if not as_json and topic in {"features", "overview", "model", "workflow-rules", "capabilities"}:
        assert text
        return
    if topic == "operations":
        assert all(phrase in text for phrase in ("gh.pr.checks", "gh.pr.merge", "gh.pr.merge.request"))
        return
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
def test_describe_uses_reader_facing_repository_guidance(handle):
    text = help_output("describe", handle)
    for phrase in (
        "workflow's GitHub repository context",
        "name another repository explicitly",
    ):
        assert phrase in text
    assert "HTTP" not in text
    payload = help_output("describe", handle, as_json=True)
    examples = {example["name"]: example for example in payload["canonical_examples"]}
    expected_name = "gh_pr_async_merge_head_context" if handle.endswith(".request") else "gh_pr_async_merge_head"
    assert set(examples) == {expected_name}
    context = examples[expected_name]
    assert (context["verification"]["world"] == "gh-pr-merge-head-context") == handle.endswith(".request")
    assert "# Supply that context through profile YAML: connectors: {gh: {repository: acme/mobile-app}}" in context.get("yaml", "") or not handle.endswith(".request")
    assert ("# Supply that context through profile YAML:" in text) == handle.endswith(".request")
    import yaml

    workflow = yaml.safe_load(context["yaml"])
    assert "connectors" not in workflow and "connector_contexts" not in workflow
    merge_steps = [step for block in workflow["blocks"] for step in block.get("steps", [])
                   if step.get("uses") in ("gh.pr.merge", "gh.pr.merge.request")]
    assert len(merge_steps) == 2
    assert all("repository" not in step["with"] for step in merge_steps) == handle.endswith(".request")
    if handle.endswith(".request"):
        assert "selected repository and pull number must match the saved request" in text


def test_merge_request_guide_describes_saved_request_outcomes_without_transport_details():
    text = help_output("describe", "connector.gh.pr.merge.request")

    for phrase in (
        "workflow's GitHub repository context",
        "Provide a valid ASCII OWNER/REPO value",
        "selected repository and pull number must match the saved request",
        "expired or missing request ID is unavailable evidence",
    ):
        assert phrase in text
    for term in ("bootstrap", "connector_contexts", "diagnostic", "HTTP", "404"):
        assert term not in text


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
