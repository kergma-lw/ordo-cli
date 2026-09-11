"""Complete PR list contracts; all external commands are mocked."""

import copy
import json
import subprocess
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import patch

import pytest

from connectors.gh.probes.pr import list as pr_list
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Workflow
from ordo.plugin_sdk import OperationContext, bootstrap_ok
from ordo.runtime.resolution import ResolvedOperation


PR = {
    "number": 42, "state": "open", "draft": False, "merged_at": None,
    "html_url": "https://github.com/owner/repo/pull/42",
    "url": "https://api.github.com/repos/owner/repo/pulls/42",
    "user": {"login": "author-not-fork-owner"},
    "head": {"ref": "feature", "sha": "a" * 40, "repo": {"full_name": "fork/repo", "owner": {"login": "fork"}}},
    "base": {"ref": "main", "sha": "b" * 40, "repo": {"full_name": "owner/repo", "name": "repo", "owner": {"login": "owner"}}},
}


def pull(number=42, **changes):
    return {**copy.deepcopy(PR), "number": number,
            "html_url": f"https://github.com/owner/repo/pull/{number}",
            "url": f"https://api.github.com/repos/owner/repo/pulls/{number}", **changes}


def link(page, *, relation="next", **filters):
    query = urlencode({"state": "all", "per_page": "100", **filters, "page": str(page)})
    return f'<https://api.github.com/repos/owner/repo/pulls?{query}>; rel="{relation}"'


def response(items=(), *, links=None, status=200, body=None, newline="\r\n", returncode=None):
    headers = [f"HTTP/2.0 {status} Status", "Content-Type: application/json"]
    if links is not None:
        headers.append(f"Link: {links}")
    text = newline.join(headers) + newline * 2 + (json.dumps(list(items)) if body is None else body)
    return subprocess.CompletedProcess([], int(status >= 400) if returncode is None else returncode, text, "")


def invoke(responses=(), *, inputs=None, repository="owner/repo"):
    ctx = OperationContext(
        resolved=ResolvedOperation(
            reference="gh.pr.list", connector_namespace="gh", source="public",
            operation=get_public_connector_registry().get_operation("gh.pr.list"),
            resolved_inputs={"state": "all"} if inputs is None else inputs,
        ),
        workflow=Workflow(version=0, workflow="pull-list"),
        bootstrap=bootstrap_ok(context={"repository": repository}),
        caller=lambda *_: pytest.fail("Unexpected operation dependency"),
    )
    with patch("subprocess.run", side_effect=list(responses)) as command:
        result = pr_list.run(ctx)
    assert command.call_count == len(responses)
    return result, [call.args[0] for call in command.call_args_list]


def unavailable(result):
    assert result.status == "pull_list_unavailable"
    assert result.outputs == {}
    assert result.diagnostics[0].level == "error"


def test_recursive_public_contract():
    operation = get_public_connector_registry().get_operation("gh.pr.list")
    assert operation.kind == "probe"
    assert set(operation.inputs) == {"repository", "state", "head", "head_owner", "base"}
    assert set(operation.outputs) == {"repository", "state", "head", "head_owner", "base", "items", "count", "complete"}
    assert operation.outputs["items"] == [pr_list._ITEM_FIELDS]
    assert set(operation.failure_modes) == {"input_error", "pull_list_unavailable"}


@pytest.mark.parametrize("size", [0, 1, 3, 100])
def test_full_terminal_page_and_context_fallback(size):
    result, calls = invoke([response([pull(n) for n in range(1, size + 1)])])
    assert result.status == "ok"
    assert result.outputs["repository"] == "owner/repo"
    assert result.outputs["count"] == size
    assert len(result.outputs["items"]) == size
    assert result.outputs["complete"] is True
    assert result.outputs["head"] is result.outputs["head_owner"] is result.outputs["base"] is None
    assert calls[0][0:8] == ["gh", "api", "--hostname", "github.com", "--method", "GET", "--include", calls[0][-1]]
    assert calls[0][-1].startswith("/repos/owner/repo/pulls?")


def test_explicit_override_preserves_warning():
    result, calls = invoke([response()], inputs={"state": "open", "repository": "other/target"})
    assert result.status == "ok"
    assert result.outputs["repository"] == "other/target"
    assert result.diagnostics[0].code.endswith("repository_override")
    assert calls[0][-1].startswith("/repos/other/target/pulls?")


@pytest.mark.parametrize("value", ["", "bad", "a/b/c", "a/b?state=all", "a/b#fragment", "a/b\n", 7, False])
def test_invalid_explicit_repository_does_not_fall_back(value):
    result, _ = invoke(inputs={"state": "all", "repository": value})
    assert result.status == "input_error"


@pytest.mark.parametrize("repository", [None, "bad"])
def test_missing_repository(repository):
    result, _ = invoke(repository=repository)
    assert result.status == "input_error"


@pytest.mark.parametrize("inputs", [
    {}, {"state": None}, {"state": "merged"}, {"state": "OPEN"}, {"state": []},
    {"state": "all", "head_owner": "fork"},
    *({"state": "all", "head": "feature", "head_owner": owner} for owner in ("", "a:b", "a/b", "a&state=all", "a b", 5)),
    *({"state": "all", key: value} for key in ("head", "base") for value in ("", "a:b", "a\nb", " a", 5)),
])
def test_invalid_filters_are_input_errors(inputs):
    result, _ = invoke(inputs=inputs)
    assert result.status == "input_error"


@pytest.mark.parametrize("state", ["open", "closed", "all"])
def test_query_encoding_and_literal_owner(state):
    head, base = "feature/雪&x=#tag", "release/é&head=wrong#x"
    result, calls = invoke([response()], inputs={"state": state, "head": head, "head_owner": "Fork-Org", "base": base})
    assert result.status == "ok"
    assert parse_qs(urlsplit(calls[0][-1]).query) == {
        "state": [state], "per_page": ["100"], "page": ["1"], "head": [f"Fork-Org:{head}"], "base": [base],
    }
    assert result.outputs["head"] == head
    assert result.outputs["head_owner"] == "Fork-Org"


def test_typed_fields_and_merge_tristate():
    unknown = pull(3)
    del unknown["merged_at"]
    result, _ = invoke([response([pull(1), pull(2, state="closed", merged_at="2026-09-11T12:00:00Z"), unknown, pull(4, state="closed")])])
    items = result.outputs["items"]
    assert [item["merged"] for item in items] == [False, True, None, False]
    assert items[0] == {
        "number": 1, "pull_ref": "owner/repo#1", "url": "https://github.com/owner/repo/pull/1",
        "state": "open", "draft": False, "merged": False, "merged_at": None,
        "head_repository": "fork/repo", "head_repository_key": "fork/repo", "head_owner": "fork", "head_ref": "feature", "head_sha": "a" * 40,
        "base_repository": "owner/repo", "base_ref": "main", "base_sha": "b" * 40,
    }


def test_forks_with_same_head_are_not_collapsed_or_confused_with_author():
    second = pull(2)
    second["head"]["repo"] = {"full_name": "other/repo", "owner": {"login": "other"}}
    result, calls = invoke([response([pull(1), second])], inputs={"state": "all", "head": "feature"})
    assert result.status == "ok"
    assert [item["head_owner"] for item in result.outputs["items"]] == ["fork", "other"]
    assert "head" not in parse_qs(urlsplit(calls[0][-1]).query)


def test_deleted_repositories_stay_unknown_even_with_owner_filter():
    node = pull()
    node["head"]["repo"] = None
    node["base"]["repo"] = None
    result, _ = invoke([response([node])], inputs={"state": "all", "head": "feature", "head_owner": "fork"})
    assert result.status == "ok"
    item = result.outputs["items"][0]
    assert item["head_repository"] is item["head_owner"] is item["base_repository"] is None
    assert item["head_repository_key"] is None


def test_owner_and_repository_case_insensitive():
    node = pull()
    node["base"]["repo"]["full_name"] = "OWNER/REPO"
    result, _ = invoke([response([node])], inputs={"state": "open", "head": "feature", "head_owner": "FORK", "base": "main"})
    assert result.status == "ok"


@pytest.mark.parametrize("field,value", [("number", True), ("number", "42"), ("number", 0), ("state", "merged"), ("state", None), ("draft", "false"), ("merged_at", False)])
def test_malformed_fields_fail_entire_list(field, value):
    result, _ = invoke([response([pull(1), pull(**{field: value})])])
    unavailable(result)


@pytest.mark.parametrize("node", [None, 42, {}, {"number": 1}, {"state": "open"}, {**PR, "head": []}, {**PR, "base": {"repo": []}}])
def test_malformed_rows(node):
    result, _ = invoke([response([node])])
    unavailable(result)


@pytest.mark.parametrize("key,value", [("head", "Feature"), ("base", "Main"), ("head_owner", "other"), ("state", "closed")])
def test_available_filter_mismatch_is_failure(key, value):
    result, _ = invoke([response([PR])], inputs={"state": "all", "head": "feature", "head_owner": "fork", key: value})
    unavailable(result)


@pytest.mark.parametrize("change", ["full_name", "owner", "name", "url", "html_url"])
def test_contradictory_target_binding(change):
    node = pull()
    if change in ("url", "html_url"):
        node[change] = node[change].replace("owner/repo", "other/repo")
    elif change == "owner":
        node["base"]["repo"]["owner"]["login"] = "other"
    else:
        node["base"]["repo"][change] = "other/repo" if change == "full_name" else "other"
    result, _ = invoke([response([node])])
    unavailable(result)


def test_short_and_empty_pages_follow_all_advertised_links():
    result, calls = invoke([
        response([pull(1)], links=link(2) + ", " + link(3, relation="last")),
        response([], links=link(3) + ", " + link(1, relation="prev"), newline="\n"),
        response([pull(2)], links=link(2, relation="prev") + ", " + link(1, relation="first")),
    ])
    assert result.status == "ok"
    assert result.outputs["count"] == 2
    assert result.outputs["complete"] is True
    assert [parse_qs(urlsplit(call[-1]).query)["page"] for call in calls] == [["1"], ["2"], ["3"]]


@pytest.mark.parametrize("links", [
    link(1), link(3), link(2, state="open"), link(2, per_page="50"),
    link(2).replace("api.github.com", "evil.test"), link(2).replace("https:", "http:"),
    link(2).replace("/pulls?", "/issues?"), link(2).replace("owner/repo", "other/repo"),
    link(2).replace("page=2", "page=2&page=2"), link(2).replace("page=2", "page=2&extra=x"),
    link(2).replace("page=2", "page=2#fragment"), link(2) + ", " + link(2),
    link(3, relation="last"), "", "not a link", link(2).replace("page=2", "page=-1"),
])
def test_unsafe_or_incomplete_pagination_fails_without_following_url(links):
    result, _ = invoke([response([PR], links=links)])
    unavailable(result)


def test_encoded_filters_survive_multipage_validation():
    filters = {"head": "fork:f/雪&x=#tag", "base": "release/é"}
    result, calls = invoke([response(links=link(2, **filters)), response()],
                           inputs={"state": "all", "head": "f/雪&x=#tag", "head_owner": "fork", "base": "release/é"})
    assert result.status == "ok"
    assert parse_qs(urlsplit(calls[-1][-1]).query)["head"] == [filters["head"]]


def test_duplicate_number_across_pages_is_drift_failure():
    result, _ = invoke([response([PR], links=link(2)), response([PR])])
    unavailable(result)
    assert "drift" in result.summary


@pytest.mark.parametrize("failed", [
    response(status=403, body='{"message":"rate limited"}'),
    response(status=500, body='{"message":"server error"}', returncode=0),
    response(body='{"message":"error with successful exit"}'),
    response(body='[{"number":42'), response(body="[] trailing"), response(body="null"),
    response(body="[" * 2000), response([pull(n) for n in range(1, 102)]),
    subprocess.CompletedProcess([], 0, "[]", ""),
    subprocess.CompletedProcess([], 0, "HTTP/2.0 200 OK\nBad header\n\n[]", ""),
    OSError("read failed"), UnicodeDecodeError("utf8", b"\xff", 0, 1, "invalid"),
])
def test_later_failure_never_returns_partial_outputs(failed):
    result, _ = invoke([response([PR], links=link(2)), failed])
    unavailable(result)
    assert len(result.raw["pages"]) == 2
    assert result.diagnostics[0].details["page"] == 2
    if isinstance(failed, subprocess.CompletedProcess):
        assert result.raw["pages"][-1]["stdout"] == failed.stdout


def test_page_ceiling_is_failure_not_partial_success():
    result, calls = invoke([response([pull(page)], links=link(page + 1)) for page in range(1, 101)])
    unavailable(result)
    assert len(calls) == 100
    assert result.diagnostics[0].code.endswith("page_limit_exceeded")


def test_exact_page_ceiling_can_complete():
    result, calls = invoke([response([pull(page)], links=link(page + 1)) for page in range(1, 100)] + [response([pull(100)])])
    assert result.status == "ok"
    assert result.outputs["count"] == 100
    assert len(calls) == 100


def canonical_link(page, repository_id=123, **kwargs):
    return link(page, **kwargs).replace("/repos/owner/repo/pulls", f"/repositories/{repository_id}/pulls")


def test_bare_head_filters_all_pages_across_owners_and_preserves_filters():
    branch, base = "feature/雪&x=#tag", "release/é&base=other#x"
    nodes = [pull(n) for n in range(1, 5)]
    for node, ref, owner in zip(nodes, ["irrelevant", branch, branch, branch.upper()], ["a", "fork", "other", "other"]):
        node["head"]["ref"] = ref
        node["head"]["repo"] = {"full_name": f"{owner}/repo"}
        node["base"]["ref"] = base
    result, calls = invoke([
        response(nodes[:1], links=link(2, state="open", base=base)),
        response(nodes[1:3], links=canonical_link(3, state="open", base=base)),
        response(nodes[3:]),
    ], inputs={"state": "open", "head": branch, "base": base})
    assert result.status == "ok"
    assert {key: result.outputs[key] for key in ("repository", "state", "head", "head_owner", "base", "count", "complete")} == {
        "repository": "owner/repo", "state": "open", "head": branch, "head_owner": None,
        "base": base, "count": 2, "complete": True,
    }
    assert [item["number"] for item in result.outputs["items"]] == [2, 3]
    assert [item["head_owner"] for item in result.outputs["items"]] == ["fork", "other"]
    for page, call in enumerate(calls, 1):
        assert urlsplit(call[-1]).path == "/repos/owner/repo/pulls"
        assert parse_qs(urlsplit(call[-1]).query) == {
            "state": ["open"], "base": [base], "per_page": ["100"], "page": [str(page)],
        }


@pytest.mark.parametrize("head", [None, {}, {"ref": None}])
def test_missing_bare_head_ref_cannot_prove_absence(head):
    result, _ = invoke([response([pull(head=head)])], inputs={"state": "all", "head": "feature"})
    unavailable(result)
    assert "required for local" in result.summary


def test_duplicate_filtered_out_rows_still_fail():
    node = pull()
    node["head"]["ref"] = "irrelevant"
    result, _ = invoke([response([node], links=link(2)), response([node])], inputs={"state": "all", "head": "feature"})
    unavailable(result)
    assert "drift" in result.summary


@pytest.mark.parametrize("with_id", [True, False])
def test_numeric_aliases_on_all_pages_keep_original_request_endpoint(with_id):
    nodes = [pull(1), pull(2)]
    if with_id:
        for node in nodes:
            node["base"]["repo"]["id"] = 123
    result, calls = invoke([
        response(nodes[:1], links=canonical_link(2) + ", " + canonical_link(2, relation="last")),
        response(nodes[1:], links=canonical_link(1, relation="prev")),
    ])
    assert result.status == "ok"
    assert result.outputs["count"] == 2
    assert all(urlsplit(call[-1]).path == "/repos/owner/repo/pulls" for call in calls)


@pytest.mark.parametrize("case", ["same_page", "later_link", "earlier_body", "later_body", "body_only", "filtered_body"])
def test_canonical_id_contradictions_fail(case):
    first, second = pull(1), pull(2)
    inputs = {"state": "all"}
    if case == "same_page":
        responses = [response([first], links=canonical_link(2) + ", " + canonical_link(3, 456, relation="last"))]
    elif case == "later_link":
        responses = [response([first], links=canonical_link(2)), response([second], links=canonical_link(1, 456, relation="prev"))]
    elif case == "earlier_body":
        first["base"]["repo"]["id"] = 456
        responses = [response([first], links=link(2)), response([second], links=canonical_link(1, relation="prev"))]
    elif case == "body_only":
        first["base"]["repo"]["id"] = 123
        second["base"]["repo"]["id"] = 456
        responses = [response([first, second])]
    else:
        second["base"]["repo"]["id"] = 456
        if case == "filtered_body":
            inputs["head"] = "wanted"
        responses = [response([first], links=canonical_link(2)), response([second])]
    result, _ = invoke(responses, inputs=inputs)
    unavailable(result)
    assert "repository ID" in result.summary


@pytest.mark.parametrize("repository_id", [True, "123", 0, -1])
def test_malformed_response_repository_id(repository_id):
    node = pull()
    node["base"]["repo"]["id"] = repository_id
    result, _ = invoke([response([node], links=canonical_link(2))])
    unavailable(result)


@pytest.mark.parametrize("repository_id", ["abc", "0", "-1", "123/other", "123%2Fother"])
def test_non_numeric_or_unsafe_aliases_fail(repository_id):
    result, _ = invoke([response(links=canonical_link(2, repository_id))])
    unavailable(result)


def test_owned_encoded_head_and_base_with_canonical_alias():
    inputs = {"state": "all", "head": "f/雪&x=#tag", "head_owner": "fork", "base": "release/é&head=x"}
    filters = {"head": f"fork:{inputs['head']}", "base": inputs["base"]}
    result, calls = invoke([response(links=canonical_link(2, **filters)), response()], inputs=inputs)
    assert result.status == "ok"
    assert parse_qs(urlsplit(calls[-1][-1]).query)["head"] == [filters["head"]]


def test_open_pr_with_merged_at_is_contradictory_even_if_locally_excluded():
    result, _ = invoke([response([pull(merged_at="2026-09-11T12:00:00Z")])],
                       inputs={"state": "all", "head": "not-this-branch"})
    unavailable(result)
    assert "merged_at" in result.summary


def test_head_repository_key_preserves_factual_repository_casing():
    node = pull()
    node["head"]["repo"] = {"full_name": "Owner/Repo", "owner": {"login": "Owner"}}
    result, _ = invoke([response([node])])
    assert result.status == "ok"
    item = result.outputs["items"][0]
    assert item["head_repository"] == "Owner/Repo"
    assert item["head_repository_key"] == "owner/repo"
    assert item["head_owner"] == "Owner"
    assert pr_list.info().outputs["items"][0]["head_repository_key"] == "string"


@pytest.mark.parametrize("stdout,stderr", [(None, None), ("HTTP/2.0 200 OK", "interrupted"), (b"HTTP/2.0 200 OK", b"interrupted\xff")])
def test_late_page_timeout_discards_partial_outputs(stdout, stderr):
    error = subprocess.TimeoutExpired(["gh", "api", "request"], 30, output=stdout, stderr=stderr)
    result, _ = invoke([response([PR], links=link(2)), error])
    unavailable(result)
    assert result.diagnostics[0].code == "probe.gh_pr_list.command_timeout"
    assert result.diagnostics[0].details["page"] == 2
    assert len(result.raw["pages"]) == 2
    raw = result.raw["pages"][-1]
    assert raw["argv"] == error.cmd
    assert raw["timeout"] == 30
    assert raw["stdout"] == (stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout)
    assert raw["stderr"] == (stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr)
