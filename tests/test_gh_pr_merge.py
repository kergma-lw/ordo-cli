"""Focused async merge contract tests. All GitHub commands are mocked."""

import json
import copy
import subprocess
from unittest.mock import patch

import pytest

from connectors.gh.actions.pr import merge
from connectors.gh.probes.pr.merge import request
from connectors.gh._pr_stack import normalize_pr_stack
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Workflow
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, bootstrap_ok
from ordo.runtime.resolution import ResolvedOperation

SHA = "6358cd125586d9def8c3e5943f23506202da81cc"
UUID = "12345678-1234-1234-1234-123456789abc"
INPUTS = {"repository": "owner/repo", "pull_number": 42, "merge_method": "squash", "expected_head_sha": SHA}
DETAILS = {"uuid": UUID, "message": "Merge pending", "merge_method": "squash", "merge_action": "direct_merge", "expected_head_sha": SHA}
ENDPOINT = "repos/owner/repo/pulls/42/merge-async"
PR = {
    "number": 42, "state": "open", "merged": False, "draft": False,
    "head": {"sha": SHA, "ref": "feature"},
    "base": {"sha": "a" * 40, "ref": "main", "repo": {
        "full_name": "owner/repo", "name": "repo", "owner": {"login": "owner"},
    }},
}


def context(module, inputs, *, bootstrap_repository="default/repo"):
    reference = "gh." + module.info().name
    return OperationContext(
        resolved=ResolvedOperation(
            reference=reference, connector_namespace="gh",
            operation=get_public_connector_registry().get_operation(reference), source="public",
            resolved_inputs=inputs,
        ),
        workflow=Workflow(version=0, workflow="async-merge"),
        bootstrap=bootstrap_ok(context={"repository": bootstrap_repository}),
        caller=lambda *_: pytest.fail("Unexpected operation dependency"),
    )


def invoke(module=merge, *, status=202, payload=None, inputs=None, stdout=None, stderr="", error=None,
           pr=PR, pre_status=200, pre_error=None, bootstrap_repository="default/repo", evidence=None):
    if inputs is None:
        inputs = INPUTS if module is merge else {"repository": "owner/repo", "pull_number": 42, "request_id": UUID}
    if payload is None:
        payload = {"status": "pending", "details": DETAILS}
    if stdout is None:
        stdout = f"HTTP/2.0 {status} Status\r\nContent-Type: application/json\r\n\r\n" + json.dumps(payload)

    def command(argv, **kwargs):
        assert kwargs.get("shell") is None
        if argv[2] == "graphql":
            assert evidence is not None, "Unexpected GraphQL read"
            if isinstance(evidence, BaseException):
                raise evidence
            if isinstance(evidence, subprocess.CompletedProcess):
                return evidence
            return subprocess.CompletedProcess(argv, 0, json.dumps(evidence), "")
        if module is merge and argv[2] == "repos/owner/repo/pulls/42":
            if pre_error:
                raise pre_error
            return subprocess.CompletedProcess(argv, int(pre_status >= 400),
                                               stdout=f"HTTP/2.0 {pre_status} Status\n\n" + json.dumps(pr), stderr="")
        if error:
            raise error
        return subprocess.CompletedProcess(argv, 1 if status >= 400 else 0, stdout=stdout, stderr=stderr)

    with patch("subprocess.run", side_effect=command) as run:
        try:
            outcome = module.run(context(module, inputs, bootstrap_repository=bootstrap_repository))
        except MappedOutcomeError as exc:
            outcome = exc.outcome
    return outcome, run


def test_nested_registry_and_preflight_contract():
    registry = get_public_connector_registry()
    action = registry.get_operation("gh.pr.merge")
    probe = registry.get_operation("gh.pr.merge.request")
    assert action.kind == "action"
    assert probe.kind == "probe"
    assert set(action.inputs) == set(INPUTS)
    assert set(probe.inputs) == {"repository", "pull_number", "request_id"}
    observation, = action.preflight_observations
    assert observation.probe == "gh.pr"
    assert observation.with_ == {"repository": "{repository}", "pull_number": "{pull_number}"}
    assert "head_sha" in observation.fields
    assert "gh.pr.*" in action.invalidates_observations


@pytest.mark.parametrize("method", ("merge", "squash", "rebase"))
def test_acceptance_transmits_sha_and_direct_merge_once_and_saves_handle(method):
    result, run = invoke(inputs={**INPUTS, "merge_method": method}, payload={
        "status": "pending", "details": {**DETAILS, "merge_method": method},
    })
    assert result.status == "ok"
    assert result.outputs["submission"] == "accepted"
    assert result.outputs["state"] == "pending"
    assert result.outputs["merged"] is False
    assert result.outputs["request_id"] == UUID
    assert result.outputs["expected_head_sha"] == SHA
    assert run.call_count == 2
    run.assert_called_with(
        ["gh", "api", ENDPOINT, "--method", "PUT", "--include",
         "-H", "Accept: application/vnd.github+json", "-H", "X-GitHub-Api-Version: 2026-03-10",
         "-f", f"sha={SHA}", "-f", f"merge_method={method}", "-f", "merge_action=direct_merge"],
        capture_output=True, text=True, check=False, cwd=None,
    )


@pytest.mark.parametrize("status", (400, 403, 404, 422))
def test_refusal_keeps_http_status_and_message(status):
    message = "Pull request is not ready" if status == 400 else "GitHub refused this request"
    result, run = invoke(status=status, payload={"message": message}, stderr=f"gh: HTTP {status}")
    assert result.status == ("merge_refused" if status == 400 else "merge_api_failed")
    assert result.outputs["submission"] == ("refused" if status == 400 else "api_failed")
    assert result.outputs["http_status"] == status
    assert result.outputs["message"] == message
    assert result.diagnostics[0].details["http_status"] == status
    assert result.raw["returncode"] == 1
    assert run.call_count == 2


def test_not_ready_details_message_preserved():
    result, _ = invoke(status=400, payload={"status": "failed", "details": {"message": "Still a draft"}})
    assert result.status == "merge_refused"
    assert result.outputs["message"] == "Still a draft"


def test_existing_exact_request_is_reusable_not_head_mismatch():
    result, run = invoke(status=409)
    assert result.status == "ok"
    assert result.outputs["submission"] == "existing"
    assert result.outputs["request_compatibility"] == "exact"
    assert result.outputs["request_id"] == UUID
    assert result.outputs["http_status"] == 409
    assert result.outputs["merged"] is False
    assert run.call_count == 2


@pytest.mark.parametrize("change", ({"merge_method": "merge"}, {"merge_action": "merge_queue"}, {"expected_head_sha": "a" * 40}))
def test_existing_different_parameters_are_conflict(change):
    result, run = invoke(status=409, payload={"status": "pending", "details": {**DETAILS, **change}})
    assert result.status == "existing_request_conflict"
    assert result.outputs["request_compatibility"] == "different"
    assert result.outputs["request_id"] == UUID
    for key, value in change.items():
        assert result.outputs[key] == value
    assert run.call_count == 2


@pytest.mark.parametrize("missing", ("merge_method", "merge_action", "expected_head_sha"))
def test_existing_incomplete_parameters_are_explicitly_unknown(missing):
    details = {key: value for key, value in DETAILS.items() if key != missing}
    result, _ = invoke(status=409, payload={"status": "pending", "details": details})
    assert result.status == "existing_request_unknown"
    assert result.outputs["request_compatibility"] == "unknown"


def test_sha_case_is_semantically_compatible():
    result, _ = invoke(status=409, inputs={**INPUTS, "expected_head_sha": SHA.upper()})
    assert result.status == "ok"


def test_existing_request_response_cannot_claim_completion_with_wrong_http_state():
    result, run = invoke(status=409, payload={
        "status": "merged", "details": {"message": "Merged", "sha": SHA},
    })
    assert result.status == "existing_request_unknown"
    assert result.outputs["merged"] is None
    assert result.outputs["merge_sha"] is None
    assert run.call_count == 2


@pytest.mark.parametrize("state", ("merged", "enqueued"))
def test_already_completed_response_does_not_invent_uuid(state):
    details = {"message": "Already " + state}
    if state == "merged":
        details["sha"] = "b" * 40
    result, run = invoke(status=200, payload={"status": state, "details": details})
    assert result.status == "ok"
    assert result.outputs["state"] == state
    assert result.outputs["merged"] is (state == "merged")
    assert result.outputs["request_id"] is None
    assert result.outputs["submission"] == "already_" + state
    assert run.call_count == 2


@pytest.mark.parametrize("kwargs", (
    {"status": 500, "payload": {"message": "Internal server error"}},
    {"status": 502, "stdout": "", "stderr": "connection reset after sending request"},
    {"error": OSError("transport unavailable")},
    {"error": subprocess.TimeoutExpired("gh", 30)},
    {"stdout": "HTTP/2.0 202 Accepted\n\n{broken"},
    {"payload": {"status": "pending", "details": {"message": "accepted"}}},
    {"status": 200, "payload": {"merged": True, "sha": SHA, "message": "synchronous shape"}},
    {"status": 202, "payload": {"status": "merged", "details": {"message": "Merged", "sha": SHA}}},
    {"status": 200, "payload": {"status": "failed", "details": {"message": "Refused"}}},
))
def test_ambiguous_mutation_never_retries_or_claims_merge(kwargs):
    result, run = invoke(**kwargs)
    assert result.status == "merge_result_unknown"
    assert result.outputs["merged"] is None
    assert result.outputs["merge_sha"] is None
    assert run.call_count == 2


@pytest.mark.parametrize("field,value", (
    ("expected_head_sha", "abc123"), ("expected_head_sha", "g" * 40),
    ("expected_head_sha", None), ("merge_method", "default"), ("merge_method", []),
    ("repository", "owner/repo?x=y"), ("pull_number", True), ("pull_number", 0),
))
def test_invalid_action_input_never_sends_request(field, value):
    result, run = invoke(inputs={**INPUTS, field: value})
    assert result.status == "input_error"
    run.assert_not_called()


@pytest.mark.parametrize("missing", ("pull_number", "merge_method", "expected_head_sha"))
def test_non_repository_action_inputs_required_even_with_bootstrap_repository(missing):
    result, run = invoke(inputs={key: value for key, value in INPUTS.items() if key != missing})
    assert result.status == "input_error"
    run.assert_not_called()


@pytest.mark.parametrize("module", (merge, request))
@pytest.mark.parametrize("explicit_null", (False, True))
def test_repository_omitted_or_null_uses_connector_context(module, explicit_null):
    inputs = {"pull_number": 42, "request_id": UUID} if module is request else {
        key: value for key, value in INPUTS.items() if key != "repository"
    }
    if explicit_null:
        inputs["repository"] = None
    result, run = invoke(module, inputs=inputs, bootstrap_repository="owner/repo",
                         status=200 if module is request else 202)
    assert result.status == "ok"
    assert result.outputs["repository"] == "owner/repo"
    assert result.outputs["pull_number"] == 42
    assert all(call.args[0][2].startswith("repos/owner/repo/pulls/42") for call in run.call_args_list)
    assert run.call_count == (1 if module is request else 2)


@pytest.mark.parametrize("module", (merge, request))
@pytest.mark.parametrize("bootstrap_repository", ("default/repo", None, "malformed context"))
def test_explicit_repository_overrides_context(module, bootstrap_repository):
    result, run = invoke(module, bootstrap_repository=bootstrap_repository,
                         status=200 if module is request else 202)
    assert result.status == "ok"
    assert result.outputs["repository"] == "owner/repo"
    assert all(call.args[0][2].startswith("repos/owner/repo/pulls/42") for call in run.call_args_list)


@pytest.mark.parametrize("module", (merge, request))
@pytest.mark.parametrize("bootstrap_repository", (None, "", "not-a-repository"))
def test_missing_resolved_repository_fails_before_api(module, bootstrap_repository):
    inputs = {"pull_number": 42, "request_id": UUID} if module is request else {
        key: value for key, value in INPUTS.items() if key != "repository"
    }
    result, run = invoke(module, inputs=inputs, bootstrap_repository=bootstrap_repository)
    assert result.status == "input_error"
    assert result.diagnostics[0].code.endswith(".repository_missing")
    run.assert_not_called()


@pytest.mark.parametrize("module", (merge, request))
@pytest.mark.parametrize("repository", ("", "bad repository", "owner/repo?x=y", 42, False))
def test_malformed_explicit_repository_does_not_fall_back(module, repository):
    inputs = {"pull_number": 42, "request_id": UUID} if module is request else dict(INPUTS)
    inputs["repository"] = repository
    result, run = invoke(module, inputs=inputs, bootstrap_repository="owner/repo")
    assert result.status == "input_error"
    assert result.diagnostics[0].code.endswith(".invalid_repository")
    run.assert_not_called()


@pytest.mark.parametrize("state", ("pending", "failed", "merged", "enqueued"))
def test_request_observes_actual_state_once(state):
    details = DETAILS if state == "pending" else {"message": "Head changed or rules refused merge" if state == "failed" else state}
    if state == "merged":
        details = {**details, "sha": "b" * 40}
    result, run = invoke(request, status=200, payload={"status": state, "details": details})
    assert result.status == "ok"  # Failed merge is observed successfully.
    assert result.outputs["state"] == state
    assert result.outputs["merged"] is (state == "merged")
    assert result.outputs["request_id"] == UUID
    assert result.outputs["message"] == details["message"]
    assert "head_mismatch" not in result.outputs
    run.assert_called_once()
    assert run.call_args.args[0][:7] == ["gh", "api", ENDPOINT + "/" + UUID, "--method", "GET", "--include", "-H"]


def test_accepted_outputs_supply_request_probe_inputs():
    accepted, submit = invoke()
    saved = {key: accepted.outputs[key] for key in ("repository", "pull_number", "request_id")}
    observed, observe = invoke(request, inputs=saved, status=200,
                               payload={"status": "merged", "details": {"message": "Merged", "sha": "b" * 40}})
    assert observed.status == "ok"
    assert observed.outputs["merged"] is True
    assert observed.outputs["merge_sha"] == "b" * 40
    assert submit.call_count == 2
    observe.assert_called_once()


@pytest.mark.parametrize("status", (403, 404, 422, 500))
def test_unavailable_observation_keeps_http_failure_without_inventing_request_failure(status):
    result, run = invoke(request, status=status, payload={"message": "Not Found"})
    assert result.status == "request_unavailable"
    assert result.outputs["state"] == "unknown"
    assert result.outputs["request_id"] == UUID
    assert result.outputs["http_status"] == status
    assert result.outputs["message"] == "Not Found"
    run.assert_called_once()


@pytest.mark.parametrize("kwargs", (
    {"error": OSError("offline")}, {"stdout": "not JSON"},
    {"payload": {"status": "surprise", "details": {"message": "unknown state"}}},
    {"payload": {"status": "merged", "details": {"message": "missing SHA"}}},
))
def test_malformed_or_transport_observation_is_unavailable(kwargs):
    result, run = invoke(request, status=200, **kwargs)
    assert result.status == "request_unavailable"
    run.assert_called_once()


@pytest.mark.parametrize("request_id", (None, "", "../other", UUID + "?query", "made-up-handle"))
def test_probe_rejects_invalid_handle_before_command(request_id):
    result, run = invoke(request, inputs={"repository": "owner/repo", "pull_number": 42, "request_id": request_id})
    assert result.status == "input_error"
    run.assert_not_called()


def assert_read_only(run):
    run.assert_called_once()
    assert run.call_args.args[0][2:5] == ["repos/owner/repo/pulls/42", "--method", "GET"]


def test_stale_head_is_observed_before_submission():
    result, run = invoke(pr={**PR, "head": {"ref": "feature", "sha": "c" * 40}})
    assert result.status == "head_mismatch"
    assert result.outputs["observed_head_sha"] == "c" * 40
    assert result.outputs["expected_head_sha"] == SHA
    assert result.outputs["submission"] == "not_submitted"
    assert_read_only(run)


def test_base_change_has_no_atomic_expected_base_guard():
    changed = {**PR, "base": {**PR["base"], "ref": "release", "sha": "d" * 40}}
    result, run = invoke(pr=changed)
    assert result.status == "ok"
    assert run.call_count == 2
    argv = run.call_args.args[0]
    assert f"sha={SHA}" in argv
    assert not any("base=" in arg or "expected_base" in arg for arg in argv)


def test_stacked_pr_is_explicitly_unsupported_without_put():
    result, run = invoke(pr={**PR, "stack": {"base": {"ref": "main", "sha": "b" * 40}, "size": 2, "position": 1}})
    assert result.status == "unsupported_stack"
    assert result.outputs["stack_scope"] == "stacked"
    assert_read_only(run)


@pytest.mark.parametrize("stack", (None, {}, [], "stack", {"base": {}}, {"base": {"ref": "main", "sha": "short"}}))
def test_untrustworthy_stack_scope_never_submits(stack):
    result, run = invoke(pr={**PR, "stack": stack})
    assert result.status == "merge_scope_unknown"
    assert_read_only(run)


@pytest.mark.parametrize("pr", (
    {}, [], {"number": 42}, {**PR, "number": 43}, {**PR, "number": True},
    {**PR, "base": {**PR["base"], "repo": {"full_name": "other/repo"}}},
    {**PR, "head": {}}, {**PR, "merged": "false"}, {**PR, "state": []},
    {key: value for key, value in PR.items() if key != "draft"},
))
def test_malformed_pr_or_wrong_identity_never_submits(pr):
    result, run = invoke(pr=pr)
    assert result.status == "merge_scope_unknown"
    assert_read_only(run)


def test_optional_stack_absence_requires_other_pr_facts():
    assert normalize_pr_stack(PR) == "standalone"
    assert normalize_pr_stack({}) == "unknown"
    assert normalize_pr_stack({**PR, "stack": None}) == "unknown"


def test_repeated_already_merged_is_read_only_even_with_unknown_stack_and_stale_head():
    pr = {**PR, "state": "closed", "merged": True,
          "stack": None, "head": {"ref": "feature", "sha": "c" * 40}}
    for _ in range(2):
        result, run = invoke(pr=pr, evidence=merged_evidence(pr))
        assert result.status == "ok"
        assert result.outputs["submission"] == "already_merged"
        assert result.outputs["merged"] is True
        assert result.outputs["request_id"] is None
        assert result.outputs["merge_sha"] == "b" * 40
        assert run.call_count == 2
        assert run.call_args.args[0][2] == "graphql"
        assert all("PUT" not in call.args[0] for call in run.call_args_list)


def merged_evidence(pr):
    return {"data": {"repository": {"nameWithOwner": "OWNER/REPO", "pullRequest": {
        "number": 42, "state": "MERGED", "merged": True,
        "headRefOid": pr["head"]["sha"].upper(), "baseRefOid": pr["base"]["sha"].upper(),
        "potentialMergeCommit": None, "mergeCommit": {"oid": "B" * 40},
    }}}}


@pytest.mark.parametrize("failure, expected_status", (
    ("errors", "merge_api_failed"),
    ("timeout", "merge_api_failed"),
    ("nonzero", "merge_api_failed"),
    ("errors_null", "merge_scope_unknown"),
    ("null", "merge_scope_unknown"),
    ("sha", "merge_scope_unknown"),
    ("head", "merge_scope_unknown"),
    ("base", "merge_scope_unknown"),
    ("repo", "merge_scope_unknown"),
    ("number", "merge_scope_unknown"),
    ("state", "merge_scope_unknown"),
    ("merged", "merge_scope_unknown"),
    ("json", "merge_scope_unknown"),
))
def test_already_merged_requires_bound_commit_evidence_without_put(failure, expected_status):
    pr = {**PR, "state": "closed", "merged": True, "stack": None}
    evidence = copy.deepcopy(merged_evidence(pr))
    repository = evidence["data"]["repository"]
    pull = repository["pullRequest"]
    if failure == "errors":
        evidence["errors"] = [{"message": "partial data"}]
    elif failure == "errors_null":
        evidence["errors"] = None
    elif failure == "null":
        pull["mergeCommit"] = None
    elif failure == "sha":
        pull["mergeCommit"] = {"oid": "short"}
    elif failure in ("head", "base"):
        pull[failure + "RefOid"] = "d" * 40
    elif failure == "repo":
        repository["nameWithOwner"] = "other/repo"
    elif failure == "number":
        pull["number"] = 43
    elif failure == "state":
        pull["state"] = "CLOSED"
    elif failure == "merged":
        pull["merged"] = False
    elif failure == "timeout":
        evidence = subprocess.TimeoutExpired("gh", 30)
    elif failure == "nonzero":
        evidence = subprocess.CompletedProcess([], 1, json.dumps(evidence), "offline")
    elif failure == "json":
        evidence = subprocess.CompletedProcess([], 0, "{broken", "")
    result, run = invoke(pr=pr, evidence=evidence)
    assert result.status == expected_status
    assert result.outputs["submission"] == "not_submitted"
    assert result.outputs["merged"] is not True
    assert result.outputs["merge_sha"] is None
    assert run.call_count == 2
    assert all("PUT" not in call.args[0] for call in run.call_args_list)


@pytest.mark.parametrize("status", (403, 404, 422, 500))
def test_pre_read_api_failure_is_not_merge_refusal_or_unknown_mutation(status):
    result, run = invoke(pre_status=status, pr={"message": "PR unavailable"})
    assert result.status == "merge_api_failed"
    assert result.outputs["submission"] == "not_submitted"
    assert result.outputs["http_status"] == status
    assert result.outputs["message"] == "PR unavailable"
    assert_read_only(run)


def test_pre_read_timeout_has_known_no_submission():
    result, run = invoke(pre_error=subprocess.TimeoutExpired("gh", 30))
    assert result.status == "merge_api_failed"
    assert result.outputs["submission"] == "not_submitted"
    assert_read_only(run)


@pytest.mark.parametrize("payload", (
    {"status": [], "details": {"message": "invalid"}},
    {"status": "pending", "details": {"message": "missing request facts"}},
    {"status": "pending", "details": {**DETAILS, "uuid": "aaaaaaaa-1234-1234-1234-123456789abc"}},
    {"status": "pending", "details": {**DETAILS, "merge_method": []}},
    {"status": "failed", "details": []},
    {"status": "enqueued", "details": {"message": None}},
))
def test_probe_rejects_invalid_status_structures(payload):
    result, run = invoke(request, status=200, payload=payload)
    assert result.status == "request_unavailable"
    run.assert_called_once()
