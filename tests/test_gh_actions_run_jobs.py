"""Direct job observation contracts, including hostile and drifting pagination."""

import json
import subprocess
from unittest.mock import patch

import pytest

from connectors.gh.probes.actions.run import jobs as actions_jobs
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Workflow
from ordo.plugin_sdk import OperationContext, bootstrap_ok
from ordo.runtime.resolution import ResolvedOperation

RUN_ID = 34835605116
PATH = f"repos/owner/repo/actions/runs/{RUN_ID}/attempts/2/jobs"


def job(number=1, **changes):
    return {"id": number, "run_id": RUN_ID, "run_attempt": 2, "name": f"job-{number}",
            "status": "completed", "conclusion": "success", "head_sha": "a" * 40,
            "check_run_url": f"https://api.github.com/repos/owner/repo/check-runs/{number + 1000}",
            "html_url": f"https://github.com/owner/repo/actions/runs/{RUN_ID}/job/{number}",
            "started_at": "2026-09-14T10:00:00Z", "completed_at": "2026-09-14T10:01:00Z", **changes}


def link(page, relation="next", path=PATH):
    return f'<https://api.github.com/{path}?per_page=100&page={page}>; rel="{relation}"'


def response(items=(), *, total=None, links=None, body=None, status=200):
    headers = [f"HTTP/2.0 {status} Status", "Content-Type: application/json"]
    if links is not None:
        headers.append(f"Link: {links}")
    body = json.dumps({"total_count": len(items) if total is None else total, "jobs": list(items)}) if body is None else body
    return subprocess.CompletedProcess([], 0, "\r\n".join(headers) + "\r\n\r\n" + body, "")


def invoke(responses=(), *, inputs=None, repository="owner/repo"):
    inputs = {"run_id": RUN_ID, "attempt": 2} if inputs is None else inputs
    ctx = OperationContext(
        resolved=ResolvedOperation(reference="gh.actions.run.jobs", connector_namespace="gh", source="public",
                                   operation=actions_jobs.info(), resolved_inputs=inputs),
        workflow=Workflow(version=0, workflow="jobs-observation"),
        bootstrap=bootstrap_ok(context={"repository": repository}),
        caller=lambda *_: pytest.fail("Unexpected dependency"),
    )
    with patch("subprocess.run", side_effect=list(responses)) as command:
        result = actions_jobs.run(ctx)
    assert command.call_count == len(responses)
    calls = [call.args[0] for call in command.call_args_list]
    for page, argv in enumerate(calls, 1):
        repo = inputs.get("repository") or repository
        assert argv[:3] == ["gh", "api", f"repos/{repo}/actions/runs/{RUN_ID}/attempts/2/jobs?per_page=100&page={page}"]
        assert "--include" in argv
        assert "--paginate" not in argv
        assert "X-GitHub-Api-Version: 2026-03-10" in argv
        assert argv[argv.index("--method") + 1] == "GET"
        assert argv[argv.index("--hostname") + 1] == "github.com"
    return result, calls


def unavailable(result):
    assert result.status == "actions_jobs_unavailable"
    assert result.outputs == {}
    assert result.diagnostics[0].code.startswith("probe.gh_actions_run.")


def test_discovery_contract_and_job_link_identity():
    operation = get_public_connector_registry().get_operation("gh.actions.run.jobs")
    assert operation.kind == "probe"
    assert set(operation.inputs) == {"repository", "run_id", "attempt"}
    assert set(operation.failure_modes) == {"input_error", "actions_jobs_unavailable"}
    result, _ = invoke([response([job()])])
    assert result.status == "ok"
    assert set(result.outputs) == set(operation.outputs) == {"repository", "run_id", "run_attempt", "items", "count", "complete"}
    assert set(result.outputs["items"][0]) == set(operation.outputs["items"][0]) == {
        "job_id", "name", "status", "conclusion", "head_sha", "check_run_id", "url", "started_at", "completed_at",
    }
    assert result.outputs["items"][0]["check_run_id"] == 1001
    assert result.outputs["count"] == 1
    assert result.outputs["complete"] is True


@pytest.mark.parametrize("size", [0, 1, 100])
def test_empty_and_single_page_are_complete(size):
    result, _ = invoke([response([job(i) for i in range(1, size + 1)])])
    assert result.status == "ok"
    assert result.outputs["complete"] is True
    assert result.outputs["count"] == size


def test_explicit_repository_overrides_context():
    result, _ = invoke([response()], inputs={"repository": "other/target", "run_id": RUN_ID, "attempt": 2})
    assert result.status == "ok"
    assert result.outputs["repository"] == "other/target"
    assert result.diagnostics[0].code.endswith("repository_override")


@pytest.mark.parametrize("value", [False, 7, "", "bad", "a/b/c", "a/b?x=1", "a/b\n"])
def test_invalid_explicit_repository_does_not_fall_back(value):
    result, _ = invoke(inputs={"repository": value, "run_id": RUN_ID, "attempt": 2})
    assert result.status == "input_error"


@pytest.mark.parametrize("repository", [None, "bad"])
def test_missing_repository(repository):
    result, _ = invoke(repository=repository)
    assert result.status == "input_error"


@pytest.mark.parametrize("inputs", [
    {}, {"run_id": RUN_ID}, {"attempt": 2},
    *({"run_id": RUN_ID, "attempt": 2, field: value} for field in ("run_id", "attempt")
      for value in (None, True, False, "2", 0, -1, 2.5, [], {})),
])
def test_strict_required_ids(inputs):
    result, _ = invoke(inputs=inputs)
    assert result.status == "input_error"


def test_nullable_metadata_and_future_statuses_do_not_infer_check_id():
    minimal = {"id": 1, "run_id": RUN_ID, "run_attempt": 2,
               "details_url": "https://github.com/owner/repo/runs/123"}
    result, _ = invoke([response([minimal, job(2, status="future", conclusion="new", check_run_url=None)])])
    assert result.status == "ok"
    first, second = result.outputs["items"]
    assert first == {**dict.fromkeys(actions_jobs.ITEM_OUTPUTS), "job_id": 1}
    assert second["status"] == "future"
    assert second["conclusion"] == "new"
    assert second["check_run_id"] is None


@pytest.mark.parametrize("field,value", [
    ("id", None), ("id", True), ("id", "1"), ("id", 0),
    ("run_id", None), ("run_id", True), ("run_id", str(RUN_ID)), ("run_id", RUN_ID + 1),
    ("run_attempt", None), ("run_attempt", True), ("run_attempt", "2"), ("run_attempt", 1),
    *[(field, {}) for field in ("name", "status", "conclusion", "html_url", "started_at", "completed_at")],
    ("head_sha", "short"), ("head_sha", "g" * 40),
])
def test_job_identity_and_metadata_are_validated(field, value):
    result, _ = invoke([response([job(**{field: value})])])
    unavailable(result)


@pytest.mark.parametrize("value", [
    "", True, 1001, "https://evil.test/repos/owner/repo/check-runs/1001",
    "https://api.github.com.evil.test/repos/owner/repo/check-runs/1001",
    "https://evil@api.github.com/repos/owner/repo/check-runs/1001",
    "https://api.github.com:443/repos/owner/repo/check-runs/1001",
    "http://api.github.com/repos/owner/repo/check-runs/1001",
    "https://api.github.com/repos/other/repo/check-runs/1001",
    "https://api.github.com/repos/owner/repo/check-runs/1001?x=1",
    "https://api.github.com/repos/owner/repo/check-runs/1001#fragment",
    "https://api.github.com/repos/owner/repo/check-runs/1001/",
    "https://api.github.com/repos/owner/repo/check-runs/0",
    "https://api.github.com/repos/owner/repo/check-runs/01001",
    "https://api.github.com/repos/owner/repo/check-runs/%31",
    "https://api.github.com/repos/owner/repo/../repo/check-runs/1001",
    "https://api.github.com/repos/owner/repo/check-runs/1001\n",
    "https://github.com/owner/repo/runs/1001",
])
def test_malformed_structured_check_link_never_becomes_evidence(value):
    result, _ = invoke([response([job(check_run_url=value)])])
    unavailable(result)


def test_two_pages_have_consistent_total_unique_jobs_and_safe_requests():
    first = response([job(i) for i in range(1, 101)], total=101, links=link(2) + ", " + link(2, "last"))
    second = response([job(101)], total=101, links=link(1, "prev") + ", " + link(1, "first"))
    result, calls = invoke([first, second])
    assert result.status == "ok"
    assert result.outputs["count"] == 101
    assert result.outputs["complete"] is True
    assert [item["job_id"] for item in result.outputs["items"]] == list(range(1, 102))
    assert len(calls) == 2


@pytest.mark.parametrize("explicit", [False, True])
def test_mixed_case_repository_accepts_lowercase_job_and_pagination_paths(explicit):
    path = PATH.replace("owner/repo", "acme/repo")
    items = [job(i, check_run_url=f"https://api.github.com/repos/acme/repo/check-runs/{i + 1000}")
             for i in range(1, 102)]
    inputs = {"run_id": RUN_ID, "attempt": 2}
    if explicit:
        inputs["repository"] = "AcMe/RePo"
    result, calls = invoke([
        response(items[:100], total=101, links=link(2, path=path) + ", " + link(2, "last", path)),
        response(items[100:], total=101, links=link(1, "prev", path) + ", " + link(1, "first", path)),
    ], inputs=inputs, repository="owner/repo" if explicit else "AcMe/RePo")
    assert result.status == "ok"
    assert result.outputs["repository"] == "AcMe/RePo"
    assert result.outputs["count"] == 101
    assert result.outputs["complete"] is True
    assert [item["check_run_id"] for item in result.outputs["items"]] == list(range(1001, 1102))
    assert all("/AcMe/RePo/" in call[2] for call in calls)


@pytest.mark.parametrize("path", [
    "repos/other/repo", "repos/acme/other", "Repos/acme/repo", "repos/%61cme/repo",
    "repos/acme/%72epo", "repos/acme/repo/..", "repos/acme/repo/", "repos/acme/repo%2f",
])
@pytest.mark.parametrize("kind", ["job", "pagination"])
def test_mixed_case_comparison_does_not_relax_repository_or_path_syntax(path, kind):
    inputs = {"repository": "AcMe/RePo", "run_id": RUN_ID, "attempt": 2}
    if kind == "job":
        payload = response([job(check_run_url=f"https://api.github.com/{path}/check-runs/1001")])
    else:
        endpoint = PATH.replace("repos/owner/repo", path)
        payload = response([job(i) for i in range(1, 101)], total=101, links=link(2, path=endpoint))
    result, calls = invoke([payload], inputs=inputs)
    unavailable(result)
    assert len(calls) == 1


@pytest.mark.parametrize("suffix", ["Check-runs/1001", "check-runs/01001", "check-runs/%31", "check-runs/1001?"])
def test_job_resource_and_id_stay_exact_with_mixed_case_repository(suffix):
    result, _ = invoke([response([job(check_run_url=f"https://api.github.com/repos/acme/repo/{suffix}")])],
                       repository="AcMe/RePo")
    unavailable(result)


@pytest.mark.parametrize("before,after", [
    ("/actions/", "/Actions/"), ("/runs/", "/Runs/"), ("/attempts/2/", "/attempts/02/"),
    ("/jobs", "/Jobs"), (str(RUN_ID), "0" + str(RUN_ID)),
    ("api.github.com", "API.github.com"), ("api.github.com", "evil@api.github.com"),
    ("page=2>", "page=%32>"), ("page=2>", "page=2#>"),
])
def test_pagination_only_repository_segments_ignore_case(before, after):
    path = PATH.replace("owner/repo", "acme/repo")
    links = link(2, path=path).replace(before, after)
    result, _ = invoke([response([job(i) for i in range(1, 101)], total=101, links=links)], repository="AcMe/RePo")
    unavailable(result)


@pytest.mark.parametrize("links", [
    None, "garbage", link(3), link(1), link(2, path="repos/other/repo/actions/runs/1/attempts/2/jobs"),
    link(2).replace("api.github.com", "evil.test"), link(2).replace("https:", "http:"),
    link(2).replace("api.github.com", "api.github.com:443"),
    link(2).replace("?per_page", "#fragment?per_page"),
    link(2).replace("per_page=100", "per_page=1"),
    link(2).replace("page=2>", "page=2&page=3>"),
    link(2).replace("page=2>", "page=2&extra=x>"),
    link(2).replace("page=2>", "page=02>"),
    link(2) + ", " + link(2), link(2) + ", " + link(3, "last"),
])
def test_hostile_or_inconsistent_pagination_links_are_not_followed(links):
    result, calls = invoke([response([job(i) for i in range(1, 101)], total=101, links=links)])
    unavailable(result)
    assert len(calls) == 1


@pytest.mark.parametrize("second", [
    response([job(101)], total=102), response([], total=101), response([job(1)], total=101),
    response([job(101, run_attempt=3)], total=101),
    response([job(101)], total=101, links=link(3)),
    subprocess.CompletedProcess([], 1, "", "rate limit exceeded"),
    subprocess.CompletedProcess([], 0, "HTTP/2.0 200 OK\n\n{broken", ""),
    OSError("offline"), subprocess.TimeoutExpired("gh", 30), UnicodeError("invalid output"),
])
def test_later_page_errors_never_publish_partial_items(second):
    first = response([job(i) for i in range(1, 101)], total=101, links=link(2))
    result, _ = invoke([first, second])
    unavailable(result)


@pytest.mark.parametrize("body", ["null", "[]", "{}", '{"total_count": true, "jobs": []}',
                                   '{"total_count": "0", "jobs": []}', '{"total_count": -1, "jobs": []}',
                                   '{"total_count": 0, "jobs": null}', '{"total_count": 1, "jobs": [null]}'])
def test_malformed_page_is_not_empty_success(body):
    result, _ = invoke([response(body=body)])
    unavailable(result)


def test_page_cap_and_truncated_pages_fail_without_partial_output():
    for page in (response([], total=1), response([job()], total=101, links=link(2)),
                 response([], total=10001, links=link(2)), response(status=403)):
        result, _ = invoke([page])
        unavailable(result)


def test_exact_page_cap_can_complete():
    responses = [response([job(i) for i in range((page - 1) * 100 + 1, page * 100 + 1)],
                          total=10000, links=link(page + 1) if page < 100 else None)
                 for page in range(1, 101)]
    result, calls = invoke(responses)
    assert result.status == "ok"
    assert result.outputs["complete"] is True
    assert result.outputs["count"] == 10000
    assert len(calls) == 100
