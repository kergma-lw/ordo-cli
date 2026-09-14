import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ordo.cli import main as cli_main
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, Workflow
from ordo.runtime import check_workflow, execute_workflow, assess_workflow_readiness, plan_workflow, review_workflow
from tests.support import STANDARD_CONNECTOR_PROVIDER


@pytest.fixture
def upstream_workflow():
    return Workflow(
        version=0,
        workflow="upstream-mode-parity",
        blocks=(GuardBlock(guards=(
            Guard(expr='git.upstream.remote == "team/origin"'),
            Guard(expr='git.upstream.remote_branch == "feature/demo" and git.upstream.branch == "feature/demo"'),
        )),),
    )


@pytest.fixture
def upstream_reads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outputs = {
        ("git", "rev-parse", "--show-toplevel"): f"{tmp_path}\n",
        ("git", "symbolic-ref", "--quiet", "HEAD"): "refs/heads/feature/demo\n",
        ("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): "team/origin/feature/demo\n",
        ("git", "config", "--get", "branch.feature/demo.remote"): "team/origin\n",
        ("git", "rev-parse", "--symbolic-full-name", "@{upstream}"): "refs/remotes/team/origin/feature/demo\n",
    }
    commands = []

    def command(argv, **kwargs):
        commands.append(tuple(argv))
        assert tuple(argv) in outputs, f"Unexpected command: {argv!r}"
        return subprocess.CompletedProcess(argv, 0, stdout=outputs[tuple(argv)], stderr="")

    with patch("subprocess.run", side_effect=command):
        yield tmp_path

    # Exact allowlist proves config/canonical reads occurred and no transport ran.
    assert set(commands) == set(outputs)


@pytest.mark.parametrize("mode", (check_workflow, review_workflow, plan_workflow, assess_workflow_readiness, execute_workflow), ids=("check", "review", "plan", "explain", "run"))
def test_nested_upstream_remote_allows_runtime_mode(mode, upstream_workflow, upstream_reads):
    result = mode(upstream_workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

    assert result.status == RuntimeStatus.OK
    verdict = result.outputs["check_snapshot"] if mode is review_workflow else result.outputs
    if mode is not execute_workflow:
        assert verdict["allowed_state"] == "allowed"
    if mode is not review_workflow:
        assert verdict["can_execute"] is True
    if mode in (plan_workflow, assess_workflow_readiness):
        assert verdict["execution_allowed"] is True
    if mode is assess_workflow_readiness:
        assert verdict["explanation"]["allowed"] is True
    assert not any(diagnostic.level == "error" for diagnostic in result.diagnostics)


def test_next_recommends_nested_upstream_using_real_explanation(upstream_workflow, upstream_reads, capsys):
    entry = SimpleNamespace(
        playbook_path=upstream_reads / ".ordo" / "ordo.yaml",
        workflow_name=upstream_workflow.workflow,
        workflow_description="Inspect nested upstream remote",
        workflow_category="inspect",
        workflow_when="Check upstream configuration",
        working_directory=upstream_reads,
    )
    activated = SimpleNamespace(
        playbook_path=entry.playbook_path,
        workflow_name=upstream_workflow.workflow,
        workflow=upstream_workflow,
        profile=None,
        working_directory=upstream_reads,
        available_profiles=None,
        profile_working_directories=None,
        diagnostics=(),
    )
    with (
        patch("sys.argv", ["ordo-playbook", "next", "--json"]),
        patch("ordo.cli.list_playbook_workflows", return_value=(entry,)),
        patch("ordo.cli.inspect_playbook_workflow", return_value=entry),
        patch("ordo.cli.activate_playbook", return_value=activated) as activate,
    ):
        exit_code = cli_main()

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    activate.assert_called_once_with(workflow_name=upstream_workflow.workflow, profile_name=None, input_overrides={}, playbook_path=None)
    payload = json.loads(captured.out)
    assert payload["mode"] == "next"
    candidate, = payload["candidates"]
    assert candidate["workflow"] == upstream_workflow.workflow
    assert candidate["allowed"] is True
    assert candidate["candidate_class"] == "ready_now"
    assert candidate["blockers"] == []
    assert payload["best_candidate"]["allowed"] is True
    assert payload["ready_now_available"] is True
