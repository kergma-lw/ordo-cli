"""Direct Actions run handler contracts with synthetic REST/GraphQL routing."""

import copy
import json
import subprocess
from unittest.mock import patch

import pytest

from connectors.gh.probes.actions import run as actions_run
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Workflow
from ordo.plugin_sdk import OperationContext, bootstrap_ok
from ordo.runtime.resolution import ResolvedOperation

RUN_ID = 34835605116
HEAD = "a" * 40
BASE = "b" * 40
ENDPOINT = f"repos/owner/repo/actions/runs/{RUN_ID}"
SUITE_ENDPOINT = "repos/owner/repo/check-suites/71"
RUN = {
    "id": RUN_ID, "repository": {"full_name": "owner/repo"}, "check_suite_id": 71,
    "check_suite_node_id": "CS_node", "run_attempt": 2, "workflow_id": 19,
    "path": ".github/workflows/ci.yml", "event": "pull_request", "status": "completed",
    "conclusion": "success", "head_sha": HEAD, "head_branch": "feature",
    "html_url": f"https://github.com/owner/repo/actions/runs/{RUN_ID}",
    "created_at": "2026-09-14T10:00:00Z", "updated_at": "2026-09-14T10:05:00Z",
    "run_started_at": "2026-09-14T10:01:00Z",
    "pull_requests": [{"number": 42, "head": {"sha": HEAD}, "base": {"sha": BASE}}],
}
SUITE = {"id": 71, "node_id": "CS_node"}
GRAPHQL = {"data": {"node": {
    "__typename": "CheckSuite", "id": "CS_node", "repository": {"nameWithOwner": "owner/repo"},
    "workflowRun": {"__typename": "WorkflowRun", "databaseId": RUN_ID, "checkSuite": {"id": "CS_node"}},
}}}


def invoke(routes=(), *, inputs=None, repository="owner/repo"):
    ctx = OperationContext(
        resolved=ResolvedOperation(
            reference="gh.actions.run", connector_namespace="gh", source="public",
            operation=actions_run.info(), resolved_inputs={"run_id": RUN_ID} if inputs is None else inputs,
        ),
        workflow=Workflow(version=0, workflow="actions-observation"),
        bootstrap=bootstrap_ok(context={"repository": repository}),
        caller=lambda *_: pytest.fail("Unexpected operation dependency"),
    )
    remaining = list(routes)

    def respond(argv, **kwargs):
        assert remaining, f"Unexpected request {argv}"
        endpoint, response = remaining.pop(0)
        assert argv[:3] == ["gh", "api", endpoint]
        assert "X-GitHub-Api-Version: 2026-03-10" in argv
        assert argv[argv.index("--hostname") + 1] == "github.com"
        assert argv[argv.index("--method") + 1] == ("POST" if endpoint == "graphql" else "GET")
        if endpoint == "graphql":
            assert "id=CS_node" in argv
            query = next(arg for arg in argv if arg.startswith("query="))
            assert "workflowRun{__typename databaseId checkSuite{id}}" in query
            assert "workflowRun{repository" not in query
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, subprocess.CompletedProcess):
            return response
        return subprocess.CompletedProcess(argv, 0, json.dumps(response), "")

    with patch("subprocess.run", side_effect=respond) as command:
        result = actions_run.run(ctx)
    assert not remaining
    return result, [call.args[0] for call in command.call_args_list]


def unavailable(result):
    assert result.status == "actions_run_unavailable"
    assert result.outputs == {}
    assert result.diagnostics[0].code.startswith("probe.gh_actions_run.")


def test_discovery_and_exact_output_contract():
    operation = get_public_connector_registry().get_operation("gh.actions.run")
    assert operation.kind == "probe"
    assert set(operation.inputs) == {"repository", "run_id", "check_suite_id", "attempt"}
    assert set(operation.failure_modes) == {"input_error", "actions_run_unavailable"}
    result, _ = invoke([(ENDPOINT, RUN), (f"{ENDPOINT}/attempts/2", RUN)])
    assert result.status == "ok"
    assert set(result.outputs) == set(operation.outputs) == {
        "repository", "found", "run_id", "check_suite_id", "run_attempt", "workflow_id", "workflow_path",
        "event", "status", "conclusion", "head_sha", "head_branch", "url", "created_at", "updated_at",
        "run_started_at", "pull_requests",
    }
    assert result.outputs["workflow_path"] == RUN["path"]
    assert result.outputs["pull_requests"] == [{"number": 42, "head_sha": HEAD, "base_sha": BASE}]
    assert result.outputs["head_sha"] == HEAD


@pytest.mark.parametrize("attempt", [None, 2])
def test_optional_null_attempt_and_explicit_attempt(attempt):
    routes = [] if attempt else [(ENDPOINT, RUN)]
    result, calls = invoke([*routes, (f"{ENDPOINT}/attempts/2", RUN)],
                           inputs={"run_id": RUN_ID, "check_suite_id": None, "attempt": attempt})
    assert result.status == "ok"
    assert len(calls) == (1 if attempt else 2)


def test_repository_override_and_case_insensitive_api_identity():
    payload = {**RUN, "repository": {"full_name": "OTHER/TARGET"}}
    endpoint = f"repos/other/target/actions/runs/{RUN_ID}/attempts/2"
    result, _ = invoke([(endpoint, payload)], inputs={"repository": "other/target", "run_id": RUN_ID, "attempt": 2})
    assert result.status == "ok"
    assert result.outputs["repository"] == "other/target"
    assert result.diagnostics[0].code.endswith("repository_override")


@pytest.mark.parametrize("value", [False, 7, "", "bad", "a/b/c", "a/b?x=1", "a/b\n"])
def test_invalid_explicit_repository_never_falls_back(value):
    result, calls = invoke(inputs={"repository": value, "run_id": RUN_ID})
    assert result.status == "input_error"
    assert calls == []


@pytest.mark.parametrize("repository", [None, "bad"])
def test_missing_repository_is_input_error(repository):
    result, _ = invoke(repository=repository)
    assert result.status == "input_error"


@pytest.mark.parametrize("inputs", [
    {}, {"run_id": None}, {"run_id": RUN_ID, "check_suite_id": 71},
    *({field: value} for field in ("run_id", "check_suite_id") for value in (True, False, "1", 0, -1, 1.5, [], {})),
    *({"run_id": RUN_ID, "attempt": value} for value in (True, "2", 0, -1, 2.5, [], {})),
])
def test_strict_identity_inputs(inputs):
    result, calls = invoke(inputs=inputs)
    assert result.status == "input_error"
    assert calls == []


@pytest.mark.parametrize("attempt", [None, 2])
def test_suite_resolution_validates_node_backreference_and_large_database_id(attempt):
    graphql = copy.deepcopy(GRAPHQL)
    graphql["errors"] = []
    graphql["data"]["node"]["repository"]["nameWithOwner"] = "OWNER/REPO"
    routes = [(SUITE_ENDPOINT, SUITE), ("graphql", graphql)]
    if attempt is None:
        routes.append((ENDPOINT, RUN))
    result, _ = invoke([*routes, (f"{ENDPOINT}/attempts/2", RUN)],
                       inputs={"check_suite_id": 71, "attempt": attempt})
    assert result.status == "ok"
    assert result.outputs["run_id"] == RUN_ID
    assert result.outputs["run_attempt"] == 2


def test_only_explicit_null_association_is_not_found():
    graphql = copy.deepcopy(GRAPHQL)
    graphql["data"]["node"]["workflowRun"] = None
    result, calls = invoke([(SUITE_ENDPOINT, SUITE), ("graphql", graphql)], inputs={"check_suite_id": 71})
    assert result.status == "ok"
    assert result.outputs == {**dict.fromkeys(actions_run.OUTPUTS), "repository": "owner/repo",
                              "found": False, "check_suite_id": 71, "pull_requests": []}
    assert len(calls) == 2


@pytest.mark.parametrize("suite", [None, [], {}, {"id": True, "node_id": "CS_node"},
                                      {"id": 72, "node_id": "CS_node"}, {"id": 71},
                                      {"id": 71, "node_id": ""}, {"id": 71, "node_id": 4}])
def test_malformed_rest_suite_is_unavailable(suite):
    result, _ = invoke([(SUITE_ENDPOINT, suite)], inputs={"check_suite_id": 71})
    unavailable(result)


@pytest.mark.parametrize("path,value", [
    ((), None), ((), []), ((), {}), (("data",), None), (("data",), []),
    (("data", "node"), None), (("data", "node"), {}), (("data", "node"), []),
    (("data", "node", "id"), "CS_wrong"), (("data", "node", "__typename"), "CheckRun"),
    (("data", "node", "repository"), None), (("data", "node", "repository", "nameWithOwner"), "other/repo"),
    (("data", "node", "workflowRun"), {}), (("data", "node", "workflowRun"), []),
    (("data", "node", "workflowRun", "__typename"), "CheckRun"),
    (("data", "node", "workflowRun", "databaseId"), True),
    (("data", "node", "workflowRun", "databaseId"), "34835605116"),
    (("data", "node", "workflowRun", "databaseId"), 0),
    (("data", "node", "workflowRun", "checkSuite"), None),
    (("data", "node", "workflowRun", "checkSuite", "id"), "CS_wrong"),
    (("errors",), [{"message": "partial data"}]), (("errors",), None), (("errors",), {}),
])
def test_graphql_malformed_partial_or_mismatched_data_fails(path, value):
    graphql = copy.deepcopy(GRAPHQL)
    if path:
        parent = graphql
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
    else:
        graphql = value
    result, _ = invoke([(SUITE_ENDPOINT, SUITE), ("graphql", graphql)], inputs={"check_suite_id": 71})
    unavailable(result)


def test_missing_association_field_is_not_null_association():
    graphql = copy.deepcopy(GRAPHQL)
    del graphql["data"]["node"]["workflowRun"]
    result, _ = invoke([(SUITE_ENDPOINT, SUITE), ("graphql", graphql)], inputs={"check_suite_id": 71})
    unavailable(result)


@pytest.mark.parametrize("field,value", [
    ("id", None), ("id", True), ("id", str(RUN_ID)), ("id", RUN_ID + 1),
    ("repository", None), ("repository", {"full_name": "other/repo"}),
    ("run_attempt", None), ("run_attempt", True), ("run_attempt", "2"), ("run_attempt", 3),
    ("check_suite_id", None), ("check_suite_id", True), ("check_suite_id", "71"), ("check_suite_id", 72),
    ("check_suite_node_id", "CS_wrong"), ("check_suite_node_id", None),
])
def test_exact_attempt_identity_drift_in_suite_lookup(field, value):
    result, _ = invoke([(SUITE_ENDPOINT, SUITE), ("graphql", GRAPHQL),
                        (f"{ENDPOINT}/attempts/2", {**RUN, field: value})],
                       inputs={"check_suite_id": 71, "attempt": 2})
    unavailable(result)


@pytest.mark.parametrize("change", [{"run_attempt": 3}, {"check_suite_id": 72}, {"id": RUN_ID + 1}])
def test_latest_is_pinned_and_rerun_drift_is_unavailable(change):
    result, calls = invoke([(ENDPOINT, RUN), (f"{ENDPOINT}/attempts/2", {**RUN, **change})])
    unavailable(result)
    assert calls[-1][2].endswith("/attempts/2")


@pytest.mark.parametrize("field", ["id", "repository", "check_suite_id", "run_attempt"])
def test_latest_missing_identity_fails_before_exact_attempt(field):
    latest = copy.deepcopy(RUN)
    del latest[field]
    result, _ = invoke([(ENDPOINT, latest)])
    unavailable(result)


def test_nullable_ancillary_fields_and_future_statuses():
    minimal = {key: RUN[key] for key in ("id", "repository", "check_suite_id", "run_attempt")}
    result, _ = invoke([(f"{ENDPOINT}/attempts/2", minimal)], inputs={"run_id": RUN_ID, "attempt": 2})
    assert result.status == "ok"
    for field in ("head_sha", "workflow_id", "workflow_path", "status", "conclusion", "url"):
        assert result.outputs[field] is None
    assert result.outputs["pull_requests"] == []
    payload = {**RUN, "status": "future_status", "conclusion": "future_conclusion"}
    result, _ = invoke([(f"{ENDPOINT}/attempts/2", payload)], inputs={"run_id": RUN_ID, "attempt": 2})
    assert result.outputs["status"] == "future_status"
    assert result.outputs["conclusion"] == "future_conclusion"


@pytest.mark.parametrize("field,value", [
    *[(field, 7) for field in ("path", "event", "status", "conclusion", "head_branch", "html_url",
                               "created_at", "updated_at", "run_started_at")],
    ("workflow_id", True), ("workflow_id", "19"), ("head_sha", "short"), ("head_sha", "g" * 40),
    ("pull_requests", None), ("pull_requests", {}), ("pull_requests", [None]),
    ("pull_requests", [{"number": True}]), ("pull_requests", [{"number": 42, "head": {"sha": "short"}}]),
])
def test_malformed_ancillary_metadata_is_not_success(field, value):
    result, _ = invoke([(f"{ENDPOINT}/attempts/2", {**RUN, field: value})], inputs={"run_id": RUN_ID, "attempt": 2})
    unavailable(result)


@pytest.mark.parametrize("failure", [
    OSError("offline"), subprocess.TimeoutExpired("gh", 30), UnicodeError("invalid output"),
    subprocess.CompletedProcess([], 0, "{broken", ""),
    subprocess.CompletedProcess([], 1, json.dumps(RUN), "HTTP 403: denied"),
    subprocess.CompletedProcess([], 1, "", "HTTP 404: not found"),
    subprocess.CompletedProcess([], 1, "", "API rate limit exceeded"),
])
@pytest.mark.parametrize("stage", ["suite", "graphql", "latest", "attempt"])
def test_api_failures_are_local_and_never_not_found(stage, failure):
    routes = [(SUITE_ENDPOINT, SUITE), ("graphql", GRAPHQL), (ENDPOINT, RUN), (f"{ENDPOINT}/attempts/2", RUN)]
    index = ["suite", "graphql", "latest", "attempt"].index(stage)
    routes = [*routes[:index], (routes[index][0], failure)]
    result, _ = invoke(routes, inputs={"check_suite_id": 71})
    unavailable(result)
