import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ordo.cli import main as cli_main
from ordo.connectors.operations import evaluate_probe
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import check_workflow, execute_workflow, explain_workflow, plan_workflow, review_workflow
from ordo.runtime.resolution import ResolvedOperation
from tests.support import STANDARD_CONNECTOR_PROVIDER


# Exercise input variants at the connector boundary, not in every runtime mode.
OPTION_REVISION = "  --output=/tmp/ordo-audit-should-not-exist  "
INVALID_REVISIONS = ("--all", OPTION_REVISION, "-n1", "--", "-")
INVALID_REV = "probe.git_commits.invalid_rev"
# The expression language does not support >=; commit counts cannot be negative.
COMMITS_GUARD = "git.commits(limit=2,rev=inputs.rev).count != -1"


@pytest.fixture
def worktree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def bootstrap_only(worktree):
    def command(argv, **kwargs):
        assert argv == ["git", "rev-parse", "--show-toplevel"], f"Unexpected command: {argv!r}"
        return subprocess.CompletedProcess(argv, 0, stdout=f"{worktree}\n", stderr="")

    with patch("subprocess.run", side_effect=command) as run:
        yield run


def commits_workflow(rev, layout):
    probe = Step(name="commits", operation=OperationRef("git.commits", with_={"limit": 2, "rev": "${inputs.rev}"}))
    later = StepBlock(steps=(Step(name="must-not-run", operation=OperationRef("shell.command", with_={"command": "exit 99"})),))
    if layout == "guard":
        blocks = (GuardBlock(guards=(Guard(expr=COMMITS_GUARD),)), later)
    elif layout == "preflight":
        blocks = (StepBlock(steps=(probe,)), GuardBlock(guards=(Guard(expr="true"),)), later)
    else:
        blocks = (GuardBlock(guards=()), StepBlock(steps=(probe,)), later)
    return Workflow(version=0, workflow="commits-input-safety", declared_inputs={"rev": {}}, inputs={"rev": rev}, blocks=blocks)


@pytest.mark.parametrize("rev", INVALID_REVISIONS)
def test_invalid_revision_is_rejected_by_real_probe_dispatch(rev, bootstrap_only):
    workflow = Workflow(
        version=0,
        workflow="commits-input-safety",
        guards=(Guard(OperationRef("git.commits", with_={"limit": 2, "rev": rev})),),
    )
    operation = get_public_connector_registry().get_operation("git.commits")
    assert operation is not None
    result = evaluate_probe(ResolvedOperation("git.commits", "git", operation, "public"), workflow)

    assert result.status == "probe_failed"
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_REV]
    assert result.diagnostics[0].level == "error"
    assert bootstrap_only.called


@pytest.mark.parametrize("layout", ("guard", "preflight"))
@pytest.mark.parametrize("mode", (check_workflow, review_workflow, plan_workflow, explain_workflow, execute_workflow), ids=("check", "review", "plan", "explain", "run"))
def test_invalid_revision_blocks_runtime_modes(layout, mode, bootstrap_only):
    result = mode(commits_workflow(OPTION_REVISION, layout), connector_provider=STANDARD_CONNECTOR_PROVIDER)
    verdict = result.outputs["check_snapshot"] if mode is review_workflow else result.outputs
    if layout == "preflight" and mode is not execute_workflow:
        # See CHECK-MODE-005/006 and test_explain_reports_read_only_preflight_failure_clearly.
        # A completed analysis request is not an authorization to execute its workflow.
        assert result.status == RuntimeStatus.OK
        assert verdict["allowed_state"] == "unknown"
        assert verdict["analysis_complete"] is False
        assert "read_only_step_failed" in verdict["incomplete_reasons"]
        assert "relevant_guard_coverage_incomplete" in verdict["incomplete_reasons"]
        if mode is review_workflow:
            assert verdict["status"] == "ok"
        tree = result.analysis_tree
        assert tree is not None
        halt, = tree.preflight_halts
        assert halt["reason"] == "read_only_step_failed"
        assert halt["step_name"] == "commits"
        assert halt["details"] == {"block_index": 0, "step_index": 0, "status": "probe_failed"}
        assert tree.preflight_step_items[0]["status"] == "halted"
        assert tree.preflight_step_items[0]["operation_status"] == "probe_failed"
        assert tree.preflight_step_items[1]["name"] == "must-not-run"
        assert tree.preflight_step_items[1]["status"] == "pending"
        assert [item["status"] for item in tree.block_items] == ["preflight_halted", "pending", "blocked"]
        if mode in (plan_workflow, explain_workflow):
            assert result.outputs["execution_allowed"] is False
            frontier = result.outputs["ready_to_run_frontier"]
            assert frontier["allowed_state"] == "unknown"
            assert frontier["prepared_node_ids"] == []
        if mode is explain_workflow:
            assert result.outputs["explanation"]["allowed"] is False
            assert result.outputs["explanation"]["category"] == "preflight_step"
            assert result.outputs["explanation"]["blockers"] == ["commits"]
    elif layout == "guard":
        assert verdict["allowed_state"] == "blocked"
        if mode is review_workflow:
            assert result.status == RuntimeStatus.OK
            assert verdict["status"] == "guard_failed"
        else:
            assert result.status == RuntimeStatus.GUARD_FAILED
    else:
        assert result.status == RuntimeStatus.EXECUTION_ERROR
        assert result.failed_step == "commits"
    if mode is not review_workflow:
        assert result.outputs["can_execute"] is False
    if mode is execute_workflow:
        assert result.outputs["executed_steps"] == []
        assert "must-not-run" in result.outputs["skipped_steps"]
    assert any(diagnostic.code == INVALID_REV and diagnostic.level == "error" for diagnostic in result.diagnostics)
    assert bootstrap_only.called


def test_invalid_revision_in_ordinary_run_step(bootstrap_only):
    result = execute_workflow(commits_workflow(OPTION_REVISION, "ordinary"), connector_provider=STANDARD_CONNECTOR_PROVIDER)

    assert result.status == RuntimeStatus.EXECUTION_ERROR
    assert result.failed_step == "commits"
    assert result.outputs["can_execute"] is False
    assert result.outputs["executed_steps"] == []
    assert "must-not-run" in result.outputs["skipped_steps"]
    assert any(diagnostic.code == INVALID_REV and diagnostic.level == "error" for diagnostic in result.diagnostics)
    assert bootstrap_only.called


@pytest.mark.parametrize("mode", (check_workflow, review_workflow, plan_workflow, explain_workflow), ids=("check", "review", "plan", "explain"))
def test_ordinary_steps_remain_static_outside_run(mode, bootstrap_only):
    result = mode(commits_workflow(OPTION_REVISION, "ordinary"), connector_provider=STANDARD_CONNECTOR_PROVIDER)

    assert result.status == RuntimeStatus.OK
    assert INVALID_REV not in repr(result)
    bootstrap_only.assert_not_called()


@pytest.mark.parametrize("layout", ("guard", "preflight"))
def test_next_uses_real_explanation_and_does_not_recommend_invalid_revision(layout, worktree, bootstrap_only, capsys):
    workflow = commits_workflow(OPTION_REVISION, layout)
    entry = SimpleNamespace(
        playbook_path=worktree / ".ordo" / "ordo.yaml",
        workflow_name=workflow.workflow,
        workflow_description="Inspect bounded commit texts",
        workflow_category="inspect",
        workflow_when="Inspect commit context",
        working_directory=worktree,
    )
    activated = SimpleNamespace(
        playbook_path=entry.playbook_path,
        workflow_name=workflow.workflow,
        workflow=workflow,
        profile=None,
        working_directory=worktree,
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
    activate.assert_called_once_with(workflow_name=workflow.workflow, profile_name=None, input_overrides={}, playbook_path=None)
    assert exit_code == 0, captured.err
    payload = json.loads(captured.out)
    assert payload["mode"] == "next"
    candidate = next(item for item in payload["candidates"] if item["workflow"] == workflow.workflow)
    assert candidate["allowed"] is False
    assert any(diagnostic["code"] == INVALID_REV and diagnostic["level"] == "error" for diagnostic in candidate["diagnostics"])
    assert candidate["candidate_class"] == ("weak_match" if layout == "guard" else "not_evaluable_now")
    assert candidate["blockers"] == ([COMMITS_GUARD] if layout == "guard" else ["commits"])
    # Ranking may return a blocked best candidate, but must not present it as executable.
    assert payload["best_candidate"]["allowed"] is False
    assert payload["ready_now_available"] is False
    assert payload["uncertainty"]["kind"] == "no_ready_now_candidate"
    assert bootstrap_only.called


@pytest.mark.parametrize("rev", ("HEAD", "HEAD~10..HEAD", "  HEAD  ", "  HEAD~10..HEAD  "))
def test_valid_revision_remains_one_normalized_operand(rev, worktree):
    workflow = Workflow(
        version=0,
        workflow="commits-input-safety",
        guards=(Guard(OperationRef("git.commits", with_={"limit": 2, "rev": rev})),),
    )
    operation = get_public_connector_registry().get_operation("git.commits")
    assert operation is not None

    def command(argv, **kwargs):
        if argv == ["git", "rev-parse", "--show-toplevel"]:
            return subprocess.CompletedProcess(argv, 0, stdout=f"{worktree}\n", stderr="")
        assert argv[:2] == ["git", "log"]
        assert argv[-1] == rev.strip()
        assert argv.count(rev.strip()) == 1
        assert "--max-count=2" in argv
        stdout = "a" * 40 + "\x1fAlice\x1f2026-07-09T12:00:00+00:00\x1fSubject\x1fBody\n\x1e"
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    with patch("subprocess.run", side_effect=command) as run:
        result = evaluate_probe(ResolvedOperation("git.commits", "git", operation, "public"), workflow)

    assert result.status == "ok"
    assert result.outputs["rev"] == rev.strip()
    assert result.outputs["count"] == 1
    assert result.outputs["items"][0]["text"] == "Subject\n\nBody"
    assert result.outputs["repository_root"] == str(worktree)
    assert sum(call.args[0][:2] == ["git", "log"] for call in run.call_args_list) == 1
