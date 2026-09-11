"""PR creation contracts: public probe reuse and a single, non-retried POST."""

import json
import subprocess
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

from connectors.gh.actions.pr import create
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Workflow
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, bootstrap_ok
from ordo.runtime.resolution import ResolvedOperation


INPUTS = {"head": "feature", "base": "main", "title": "New PR", "draft": False}


def payload(repo="owner/repo", source=None, **changes):
    return {"number": 42, "state": "open", "draft": False, "title": "New PR",
            "html_url": f"https://github.com/{repo}/pull/42", "merged_at": None,
            "head": {"ref": "feature", "sha": "a" * 40, "repo": {"full_name": source or repo}},
            "base": {"ref": "main", "sha": "b" * 40, "repo": {"full_name": repo}}, **changes}


def row(repo="owner/repo", source=None, number=42, **changes):
    source = source or repo
    return {"number": number, "state": "open", "draft": False,
            "url": f"https://github.com/{repo}/pull/{number}", "pull_ref": f"{repo}#{number}",
            "head_repository": source, "head_repository_key": source.lower(),
            "head_ref": "feature", "base_repository": repo, "base_ref": "main", **changes}


def listing(items=(), **changes):
    return OperationOutcome(status="ok", outputs={
        "repository": "owner/repo", "head": "feature", "head_owner": "owner", "base": "main",
        "state": "open", "complete": True, "count": len(items), "items": list(items), **changes,
    })


def response(data=None, status=201, text=None):
    return subprocess.CompletedProcess([], int(status >= 400),
        text if text is not None else f"HTTP/2.0 {status} Status\r\nContent-Type: application/json\r\n\r\n" + json.dumps(payload() if data is None else data), "")


def context(inputs, caller, repository="owner/repo"):
    return OperationContext(
        resolved=ResolvedOperation(reference="gh.pr.create", connector_namespace="gh", source="public",
            operation=get_public_connector_registry().get_operation("gh.pr.create"), resolved_inputs=inputs),
        workflow=Workflow(version=0, workflow="pr-create"),
        bootstrap=bootstrap_ok(context={"repository": repository}), caller=caller,
    )


def invoke(*responses, inputs=None, before=None, repository="owner/repo"):
    caller = Mock(return_value=before or listing())
    with patch("subprocess.run", side_effect=list(responses)) as command:
        result = create.run(context(dict(INPUTS) if inputs is None else inputs, caller, repository))
    assert command.call_count == len(responses)
    return result, caller, [call.args[0] for call in command.call_args_list]


def test_context_and_public_probe_reuse_then_one_post():
    result, caller, calls = invoke(response())
    assert result.status == "ok" and result.outputs["created"] is True
    caller.assert_called_once_with("gh.pr.list", {
        "repository": "owner/repo", "head": "feature", "head_owner": "owner", "base": "main", "state": "open",
    })
    assert calls[0][:8] == ["gh", "api", "--hostname", "github.com", "--method", "POST", "--include", "/repos/owner/repo/pulls"]
    assert "head=feature" in calls[0] and "draft=false" in calls[0] and "body=" in calls[0]
    assert "X-GitHub-Api-Version: 2026-03-10" in calls[0]
    assert not any(arg.startswith("head_repo=") for arg in calls[0])
    assert result.outputs["pull_ref"] == "owner/repo#42"
    assert set(result.outputs) == set(create.OUTPUTS)


def test_override():
    result, caller, calls = invoke(response(payload(repo="other/target")),
        inputs={**INPUTS, "repository": "other/target"},
        before=listing(repository="other/target", head_owner="other"))
    assert result.status == "ok"
    assert caller.call_args.args[1]["repository"] == "other/target"
    assert "/repos/other/target/pulls" in calls[0]
    assert result.diagnostics[0].code.endswith("repository_override")


@pytest.mark.parametrize("key,value", [
    ("repository", "x/y?x"), ("head_repository", None), ("head_repository", "x/y/z"),
    ("head_repository", "x_y/repo"), ("head_owner", "fork"), ("head_owner", "owner:injected"), ("head_owner", None),
    ("head", "owner:branch"), ("head", ""), ("base", "a:b"), ("head", "main"), ("head", "a\nb"),
    ("title", "  "), ("title", None), ("title", "a\x00b"), ("body", None), ("body", 3),
    ("draft", None), ("draft", "false"), ("draft", 0),
])
def test_invalid_inputs_never_probe(key, value):
    result, caller, _ = invoke(inputs={**INPUTS, key: value})
    assert result.status == "input_error" and result.outputs["created"] is False
    caller.assert_not_called()


@pytest.mark.parametrize("key", ["head", "base", "title", "draft"])
def test_missing_required_input(key):
    inputs = dict(INPUTS)
    del inputs[key]
    result, caller, _ = invoke(inputs=inputs)
    assert result.status == "input_error"
    caller.assert_not_called()


@pytest.mark.parametrize("repository", [None, " owner/repo "])
def test_repository_uses_standard_null_fallback_and_explicit_normalization(repository):
    result, caller, calls = invoke(response(), inputs={**INPUTS, "repository": repository})
    assert result.status == "ok"
    assert result.outputs["repository"] == "owner/repo"
    assert caller.call_args.args[1]["repository"] == "owner/repo"
    assert "/repos/owner/repo/pulls" in calls[0]


@pytest.mark.parametrize("assertion", [{}, {"head_owner": "OWNER"}])
def test_exact_same_org_source_sends_repo_name(assertion):
    result, caller, calls = invoke(response(payload(source="Owner/fork")),
        inputs={**INPUTS, "head_repository": "Owner/fork", **assertion}, before=listing(head_owner="Owner"))
    assert result.status == "ok"
    assert caller.call_args.args[1]["head_owner"] == "Owner"
    assert "head=Owner:feature" in calls[0] and "head_repo=fork" in calls[0]


def test_explicit_other_owner_and_same_repo_casing():
    result, caller, calls = invoke(response(payload(source="fork/source")),
        inputs={**INPUTS, "head_repository": "fork/source"}, before=listing(head_owner="fork"))
    assert result.status == "ok" and "head_repo=source" in calls[0]
    assert caller.call_args.args[1]["head_owner"] == "fork"
    result, _, calls = invoke(response(), inputs={**INPUTS, "head_repository": "OWNER/REPO", "head_owner": "owner"})
    assert result.status == "ok" and "head=feature" in calls[0]


def test_existing_draft_ignores_requested_draft_and_title():
    result, _, _ = invoke(before=listing([row(draft=True)]))
    assert result.status == "already_exists" and result.outputs["created"] is False
    assert result.outputs["draft"] is True and result.outputs["pull_number"] == 42
    assert result.outputs["url"] == "https://github.com/owner/repo/pull/42"


def test_known_different_fork_does_not_block():
    result, _, _ = invoke(response(), before=listing([row(source="owner/different")]))
    assert result.status == "ok"


def test_multiple_exact_matches_are_ambiguous():
    result, _, _ = invoke(before=listing([row(), row(number=43)]))
    assert result.status == "ambiguous" and result.outputs["created"] is False


@pytest.mark.parametrize("changes", [
    {"complete": False}, {"complete": 1}, {"count": True}, {"count": -1}, {"count": 1},
    {"items": None}, {"repository": "other/repo"}, {"state": "all"}, {"head": None}, {"head_owner": None},
])
def test_incomplete_or_malformed_precheck(changes):
    before = listing()
    before.outputs.update(changes)
    result, _, _ = invoke(before=before)
    assert result.status == "precheck_failed"


@pytest.mark.parametrize("changes", [
    {"head_repository": None}, {"head_repository_key": None}, {"base_repository": None}, {"head_ref": None},
    {"state": "closed"}, {"draft": None}, {"base_ref": "other"}, {"url": "https://evil.test/42"},
    {"head_owner": "wrong"}, {"number": True}, {"merged_at": "date"},
])
def test_unknown_or_contradictory_row_fails_even_for_other_fork(changes):
    result, _, _ = invoke(before=listing([row(source="owner/other", **changes)]))
    assert result.status == "precheck_failed"


def test_precheck_failed_status_and_command_errors():
    result, _, _ = invoke(before=OperationOutcome(status="pull_list_unavailable"))
    assert result.status == "precheck_failed"
    for exc in (MappedOutcomeError(OperationOutcome(status="execution_error")), subprocess.TimeoutExpired([], 3)):
        ctx = context(INPUTS, Mock(side_effect=exc))
        with patch("subprocess.run") as command:
            result = create.run(ctx)
        command.assert_not_called()
        assert result.status == "precheck_failed" and result.raw["phase"] == "precheck"


@pytest.mark.parametrize("repository", [None, "bad", "bad_owner/repo"])
def test_invalid_or_absent_context_repository(repository):
    result, caller, _ = invoke(repository=repository)
    assert result.status == "input_error"
    caller.assert_not_called()


@pytest.mark.parametrize("status,message,expected", [
    (422, "A pull request already exists", "create_refused"), (422, "No commits between branches", "create_refused"),
    (403, "Forbidden", "api_failed"), (404, "Not Found", "api_failed"), (503, "Unavailable", "creation_unknown"),
])
def test_http_errors_no_retry_or_duplicate_requery(status, message, expected):
    errors = [{"resource": "PullRequest", "code": "custom", "message": message}]
    result, caller, calls = invoke(response({"message": message, "errors": errors}, status))
    assert result.status == expected and result.outputs["created"] is (None if status == 503 else False)
    assert result.outputs["errors"] == errors and result.outputs["message"] == message
    assert result.outputs["http_status"] == status
    assert caller.call_count == len(calls) == 1


@pytest.mark.parametrize("result", [subprocess.TimeoutExpired([], 3, output=b"secret"), OSError("secret"),
    response(text="not HTTP"), response(text="HTTP/2 201 OK\n\n{"), response([], 201)])
def test_transport_and_malformed_responses_unknown(result):
    outcome, _, _ = invoke(result)
    assert outcome.status == "creation_unknown" and outcome.outputs["created"] is None
    assert "secret" not in json.dumps(outcome.raw)


@pytest.mark.parametrize("path,value", [
    (("base", "repo", "full_name"), "other/target"), (("head", "repo", "full_name"), "fork/other"),
    (("head", "ref"), "wrong"), (("base", "ref"), "wrong"), (("head", "sha"), None),
    (("draft",), True), (("title",), "wrong"), (("number",), True), (("state",), "closed"),
])
def test_bad_201_identity_is_unknown(path, value):
    data = payload()
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    result, _, _ = invoke(response(data))
    assert result.status == "creation_unknown" and result.outputs["created"] is None
    assert result.outputs["pull_number"] is None


def test_literal_text_refs_and_explicit_true():
    head, base, title, body = "f/雪&x=#tag", "release/é&head=x", "@title-file", "@body-file\n$(touch /tmp/no)"
    data = payload(title=title, draft=True)
    data["head"]["ref"], data["base"]["ref"] = head, base
    result, _, calls = invoke(response(data), inputs={"head": head, "base": base, "title": title, "body": body, "draft": True},
        before=listing(head=head, base=base))
    assert result.status == "ok"
    for key, value in (("title", title), ("body", body), ("head", head), ("base", base)):
        index = calls[0].index(f"{key}={value}")
        assert calls[0][index - 1] == "-f"
    assert "draft=true" in calls[0]
    assert body not in json.dumps(result.raw)


def test_repeat_second_call_observes_created_pr_and_stops():
    caller = Mock(side_effect=[listing(), listing([row()])])
    ctx = context(INPUTS, caller)
    with patch("subprocess.run", return_value=response()) as command:
        first, second = create.run(ctx), create.run(ctx)
    assert first.status == "ok" and second.status == "already_exists"
    assert caller.call_count == 2 and command.call_count == 1


def test_public_metadata():
    operation = get_public_connector_registry().get_operation("gh.pr.create")
    assert operation.kind == "action" and operation.invalidates_observations == ("gh.*",)
    observation = operation.preflight_observations[0]
    assert observation.probe == "gh.pr.list" and observation.with_["state"] == "open"
    assert "head_owner" not in observation.with_


def test_real_family_adapter_reuses_public_list_with_explicit_filters():
    from ordo.connectors.operations import execute_action

    ctx = context({**INPUTS, "repository": "owner/repo"}, Mock())
    # Family bootstrap is mocked; dispatch, SDK caller, public probe and command
    # adapter are real. No CLI/network call can escape this subprocess mock.
    with patch("connectors.gh.bootstrap.run", return_value=bootstrap_ok(context={"repository": "owner/repo"})), \
         patch("subprocess.run", side_effect=[response([], 200), response()]) as command:
        result = execute_action(ctx._resolved, ctx._workflow)
    assert result.status == "ok", result
    assert command.call_count == 2
    get, post = [call.args[0] for call in command.call_args_list]
    assert "GET" in get and "POST" in post
    endpoint = next(arg for arg in get if arg.startswith("/repos/"))
    assert parse_qs(urlsplit(endpoint).query) == {
        "head": ["owner:feature"], "base": ["main"], "state": ["open"], "per_page": ["100"], "page": ["1"],
    }
