"""Reader-facing regression coverage for repaired GitHub operation help."""

import contextlib
import io
import json

from ordo.help_cli import main
from tools.build_help_site_docs import render_operation


def describe(handle):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main(["describe", handle]) == 0
    return output.getvalue()


def test_pr_create_explains_cross_repository_identity_and_outcomes():
    text = describe("connector.gh.pr.create")
    for phrase in (
        "head_repository", "exact source repository", "head_owner", "source repository's owner",
        "pull request number or URL", "creation is confirmed", "outcome is unknown",
    ):
        assert phrase in text


def test_authored_github_input_and_result_guidance_is_not_repeated_generically():
    text = describe("connector.gh.pr.create")

    assert "Input status:" not in text
    assert "Usable result facts:" not in text
    assert "`head`: required" in text
    assert "A confirmed creation returns" in text


def test_pr_list_explains_selection_facts_and_closed_merge_boundary():
    text = describe("connector.gh.pr.list")
    for phrase in (
        "pull_ref", "head_repository_key", "head_sha", "base_sha", "complete and count",
        "closed pull request is not necessarily merged", "do not infer a merge from closed state",
    ):
        assert phrase in text


def test_project_field_setters_explain_project_selection_inputs_results_and_concurrency_boundary():
    for handle, requested in (
        ("connector.gh.project.issue.field_number.set", "numeric value"),
        ("connector.gh.project.issue.field_single_select.set", "visible option label"),
    ):
        text = describe(handle)
        for phrase in ("What to provide", "Project ID", requested, "project number", "project view command", "connector.gh.project", "Project item", "changed=false", "Observe again"):
            assert phrase.lower() in text.lower(), (handle, phrase)
        assert "connector_contexts" not in text


def test_merge_help_uses_outcome_language_without_transport_or_implementation_terms():
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main(["describe", "connector.gh.pr.merge", "--json"]) == 0
    text = json.dumps(json.loads(output.getvalue())["human"])
    for phrase in ("expected_head_sha", "40-character commit ID", "gh.pr.head_sha", "request_id", "submission", "observed_head_sha", "unknown result", "not proof of completion"):
        assert phrase in text
    for phrase in ("candidate M", "base B", "head H", "CI-to-merge", "HTTP", "diagnostic", "API"):
        assert phrase not in text


def test_focused_pr_examples_are_shared_by_cli_and_site():
    from ordo.help_cli import build_operation_response

    for handle, example_name in (
        ("connector.gh.pr.list", "gh_pr_list_exactly_one_open"),
        ("connector.gh.pr.merge", "gh_pr_async_merge_head"),
    ):
        text = describe(handle)
        payload = build_operation_response(handle.removeprefix("connector."))
        assert payload is not None
        site = render_operation("operations/gh/example.md", payload)
        assert "canonical examples:" in text
        assert example_name in text
        assert example_name in site
        example, = payload["canonical_examples"]
        assert example["yaml"] in site
        for term in ("fixture", "SDK", "handler", "bootstrap"):
            assert term not in text, (handle, term)
