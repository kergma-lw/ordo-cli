import json
import subprocess
from unittest.mock import patch

import pytest

from connectors.gh.probes.actions.run import search
from ordo.model.workflow import Workflow
from ordo.plugin_sdk import OperationContext, bootstrap_ok
from ordo.runtime.resolution import ResolvedOperation


def run(pages, inputs=None):
    ctx = OperationContext(resolved=ResolvedOperation(reference="gh.actions.run.search", connector_namespace="gh", source="public", operation=search.info(), resolved_inputs=inputs or {"workflow":"deploy.yml","event":"workflow_dispatch","ref":"main","request_id":"req-1"}), workflow=Workflow(version=0, workflow="x"), bootstrap=bootstrap_ok(context={"repository":"owner/repo"}), caller=lambda *_: pytest.fail())
    queue = list(pages)
    def command(argv, **_):
        payload, link = queue.pop(0)
        headers = "Content-Type: application/json\n" + (f"Link: {link}\n" if link else "")
        return subprocess.CompletedProcess(argv, 0, f"HTTP/2 200 OK\n{headers}\n{json.dumps(payload)}", "")
    with patch("subprocess.run", side_effect=command): result = search.run(ctx)
    assert not queue
    return result


def payload(runs, total=None): return {"total_count": len(runs) if total is None else total, "workflow_runs": runs}
def item(number, name="req-1"):
    return {"id":number,"run_attempt":1,"display_title":name,"event":"workflow_dispatch","head_branch":"main","status":"queued","conclusion":None,"html_url":f"https://github.com/owner/repo/actions/runs/{number}","repository":{"full_name":"owner/repo"}}


def test_zero_one_many_and_exact_correlation():
    assert run([ (payload([]), "") ]).outputs["count"] == 0
    assert run([ (payload([item(1)]), "") ]).outputs["count"] == 1
    result = run([ (payload([item(1), item(2), item(3, "req-10")]), "") ])
    assert result.outputs["count"] == 2


def test_pagination_preserves_filters_and_requires_complete_pages():
    link = '<https://api.github.com/repos/owner/repo/actions/workflows/deploy.yml/runs?branch=main&event=workflow_dispatch&per_page=100&page=2>; rel="next", <https://api.github.com/repos/owner/repo/actions/workflows/deploy.yml/runs?branch=main&event=workflow_dispatch&per_page=100&page=2>; rel="last"'
    result = run([(payload([item(n) for n in range(1,101)], 101), link), (payload([item(101)], 101), "")])
    assert result.outputs["count"] == 101
    assert result.outputs["complete"] is True


@pytest.mark.parametrize("bad", [payload([item(1)], 2), {"total_count":1,"workflow_runs":{}}])
def test_malformed_or_nonmatching_responses_are_not_success(bad):
    result = run([(bad, "")])
    assert result.status == "actions_run_search_unavailable"
