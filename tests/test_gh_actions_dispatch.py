"""Workflow-dispatch action contracts without live GitHub access."""

import subprocess
from unittest.mock import patch

import pytest

from connectors.gh.actions import dispatch
from ordo.model.workflow import Workflow
from ordo.plugin_sdk import OperationContext, bootstrap_ok
from ordo.runtime.resolution import ResolvedOperation


def invoke(response, *, inputs=None, repository="owner/repo"):
    operation = dispatch.info()
    ctx = OperationContext(
        resolved=ResolvedOperation(
            reference="gh.actions.dispatch", connector_namespace="gh", source="public", operation=operation,
            resolved_inputs=inputs or {"workflow": "deploy.yml", "ref": "main", "inputs": {"dry_run": True}, "request_id": "dispatch-1"},
        ),
        workflow=Workflow(version=0, workflow="dispatch"),
        bootstrap=bootstrap_ok(context={"repository": repository}),
        caller=lambda *_: pytest.fail("Unexpected operation dependency"),
    )
    patched = {"side_effect": response} if isinstance(response, BaseException) else {"return_value": response}
    with patch("subprocess.run", **patched) as command:
        result = dispatch.run(ctx)
    return result, command.call_args_list


def response(status, body="", *, returncode=0):
    reason = {200: "OK", 204: "No Content", 400: "Bad Request", 403: "Forbidden", 422: "Unprocessable Entity", 500: "Server Error"}[status]
    stdout = f"HTTP/2 {status} {reason}\nX-Test: true\n\n{body}"
    return subprocess.CompletedProcess([], returncode, stdout, "")


def test_contract_and_confirmed_dispatch_include_typed_inputs():
    operation = dispatch.info()
    assert operation.kind == "action"
    assert operation.inputs == {"repository": "string", "workflow": "string", "ref": "string", "inputs": "object", "request_id": "string"}
    assert operation.failure_modes == ("input_error", "dispatch_refused", "dispatch_unknown")
    result, calls = invoke(response(200, '{"workflow_run_id":900,"run_url":"https://api.github.com/run/900","html_url":"https://github.com/owner/repo/actions/runs/900"}'), inputs={
        "workflow": "deploy.yml", "ref": "release", "inputs": {"environment": "production", "dry_run": True}, "request_id": "release-1",
    })
    assert result.status == "ok"
    assert result.outputs == {
        "repository": "owner/repo", "workflow": "deploy.yml", "ref": "release", "request_id": "release-1", "submission": "submitted",
        "run_id": 900, "url": "https://github.com/owner/repo/actions/runs/900", "http_status": 200,
        "message": None, "errors": None,
    }
    argv = calls[0].args[0]
    assert argv[:7] == ["gh", "api", "--hostname", "github.com", "--method", "POST", "--include"]
    assert "/repos/owner/repo/actions/workflows/deploy.yml/dispatches" in argv
    assert "ref=release" in argv
    assert "inputs[environment]=production" in argv and "inputs[dry_run]=true" in argv
    assert argv[argv.index("inputs[environment]=production") - 1] == "-f"
    assert argv[argv.index("inputs[dry_run]=true") - 1] == "-F"


def test_legacy_empty_acceptance_is_still_confirmed_submission():
    result, _ = invoke(response(204))
    assert result.status == "ok"
    assert result.outputs["submission"] == "submitted"
    assert result.outputs["run_id"] is None


@pytest.mark.parametrize("status", (400, 403, 422))
def test_confirmed_github_refusal_is_not_unknown(status):
    result, _ = invoke(response(status, '{"message":"not allowed","errors":["reason"]}', returncode=1))
    assert result.status == "dispatch_refused"
    assert result.outputs["submission"] == "refused"
    assert result.outputs["http_status"] == status
    assert result.outputs["message"] == "not allowed"


@pytest.mark.parametrize("inputs", [
    {"workflow": "../deploy.yml", "ref": "main", "inputs": {}},
    {"workflow": "deploy.yml", "ref": "", "inputs": {}},
    {"workflow": "deploy.yml", "ref": "main", "inputs": {"bad[name]": "x"}},
    {"workflow": "deploy.yml", "ref": "main", "inputs": {"nested": {"value": "x"}}},
    {"workflow": "deploy.yml", "ref": "main", "inputs": {str(number): "x" for number in range(26)}},
])
def test_invalid_dispatch_inputs_submit_nothing(inputs):
    result, calls = invoke(response(200, "{}"), inputs=inputs)
    assert result.status == "input_error"
    assert result.outputs["submission"] == "unknown"
    assert calls == []


@pytest.mark.parametrize("failure", [
    subprocess.TimeoutExpired("gh", 30),
    subprocess.CompletedProcess([], 0, "HTTP/2 200 OK\n\n{}", ""),
    response(200, "{}"),
    response(500, '{"message":"server"}', returncode=1),
])
def test_transport_or_untrusted_response_is_unknown(failure):
    result, _ = invoke(failure)
    assert result.status == "dispatch_unknown"
    assert result.outputs["submission"] == "unknown"


def test_dispatch_help_is_reader_facing_and_has_a_verified_example():
    from ordo.help_cli import build_operation_response
    from ordo.model.help_snippets import describe_help_snippets
    from ordo.runtime.help_snippet_runner import verify_help_snippet

    payload = build_operation_response("gh.actions.dispatch")
    assert payload is not None
    assert payload["snippet_coverage"] == "runner_verified"
    example, = describe_help_snippets()["connector.gh.actions.dispatch"]["canonical_examples"]
    result = verify_help_snippet(
        snippet=example["yaml"], world="gh-actions-dispatch", target="connector.gh.actions.dispatch",
        insertion_mode="workflow_fragment",
    )
    assert result.status == "ok"
