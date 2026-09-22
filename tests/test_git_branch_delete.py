"""Branch deletion contract against disposable repositories, never the project repo."""

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ordo.cli import main as cli_main
from ordo.connectors.operations import execute_action
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import OperationRef, Step, Workflow
from ordo.runtime import assess_workflow_readiness, check_workflow, execute_workflow, plan_workflow, review_workflow
from ordo.runtime.resolution import ResolvedOperation
from tests.support import STANDARD_CONNECTOR_PROVIDER


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("LC_ALL", "C")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(key, raising=False)

    def git(*args, check=True):
        return subprocess.run(
            ["git", "-c", "user.name=Ordo Test", "-c", "user.email=ordo@example.test", *args],
            cwd=tmp_path, capture_output=True, text=True, check=check,
        )

    git("init", "-b", "main")
    git("commit", "--allow-empty", "-m", "base")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    return tmp_path, git


def workflow(branch="topic", **inputs):
    return Workflow(version=0, workflow="delete-test", steps=(
        Step(name="delete", operation=OperationRef("git.branch.delete", with_={"branch": branch, **inputs})),
    ))


def delete(branch="topic", **inputs):
    operation = get_public_connector_registry().get_operation("git.branch.delete")
    assert operation is not None
    return execute_action(ResolvedOperation(
        "git.branch.delete", "git", operation, "public",
        resolved_inputs={"branch": branch, **inputs},
    ), workflow(branch, **inputs))


def exists(git, branch="topic"):
    return git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0


@pytest.mark.parametrize("inputs,flag", (({}, "-d"), ({"force": False}, "-d"), ({"force": True}, "-D")))
def test_ancestor_branch_deletion(repo, inputs, flag):
    _, git = repo
    git("branch", "topic")
    git("commit", "--allow-empty", "-m", "advance main")
    result = delete(**inputs)
    assert result.status == "ok"
    assert result.outputs == {"branch": "topic"}
    assert not exists(git)
    assert result.raw["argv"] == ["git", "branch", flag, "topic"]


@pytest.mark.parametrize("inputs", ({}, {"force": False}))
def test_squash_merged_branch_requires_explicit_force(repo, inputs):
    root, git = repo
    git("checkout", "-b", "topic")
    (root / "feature.txt").write_text("feature\n")
    git("add", "feature.txt")
    git("commit", "-m", "feature")
    git("checkout", "main")
    git("merge", "--squash", "topic")
    git("commit", "-m", "squash feature")
    assert git("merge-base", "--is-ancestor", "topic", "main", check=False).returncode == 1
    result = delete(**inputs)
    assert result.status == "branch_not_merged"
    assert exists(git)
    assert result.raw["stderr"]
    assert delete(force=True).status == "ok"
    assert not exists(git)


@pytest.mark.parametrize("inputs", ({}, {"force": False}, {"force": True}))
@pytest.mark.parametrize("case,expected", (
    ("missing", "branch_not_found"),
    ("current", "branch_checked_out"),
    ("worktree", "branch_checked_out"),
    ("default", "default_branch_protected"),
))
def test_force_preserves_branch_protections(repo, inputs, case, expected):
    root, git = repo
    if case != "missing":
        git("branch", "topic")
    if case == "current":
        git("checkout", "topic")
    elif case == "worktree":
        git("worktree", "add", str(root / "linked"), "topic")
    elif case == "default":
        # Protection follows origin/HEAD, not a hardcoded main/master name.
        git("update-ref", "refs/remotes/origin/topic", "topic")
        git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/topic")
    result = delete(**inputs)
    assert result.status == expected
    assert exists(git) is (case != "missing")
    if case == "worktree":
        assert result.raw["stderr"]


def test_absent_origin_head_does_not_invent_default_protection(repo):
    _, git = repo
    git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    git("checkout", "-b", "topic")
    assert delete("main", force=True).status == "ok"
    assert not exists(git, "main")


@pytest.mark.parametrize("force", (None, "true", "false", "", 0, 1, 0.0, [], {}))
def test_invalid_force_fails_without_deletion(repo, force):
    _, git = repo
    git("branch", "topic")
    result = delete(force=force)
    assert result.status == "input_error"
    assert result.diagnostics[0].code == "action.git.branch_delete.invalid_force"
    assert exists(git)
    # Also exercise runtime materialization, including explicit YAML-like null.
    result = execute_workflow(workflow(force=force), connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.status == RuntimeStatus.EXECUTION_ERROR
    assert any(d.code == "action.git.branch_delete.invalid_force" for d in result.diagnostics)
    assert exists(git)


def test_unresolved_force_is_not_silently_defaulted(repo):
    _, git = repo
    git("branch", "topic")
    operation = get_public_connector_registry().get_operation("git.branch.delete")
    result = execute_action(ResolvedOperation(
        "git.branch.delete", "git", operation, "public",
        declared_with={"branch": "topic", "force": "${inputs.absent}"},
    ), workflow())
    assert result.status == "input_error"
    assert exists(git)


@pytest.mark.parametrize("force", (False, True))
@pytest.mark.parametrize("failure", ("nonzero", "os_error"))
def test_unclassified_git_errors_retain_action_failed_normalization_and_evidence(repo, force, failure):
    _, git = repo
    git("branch", "topic")
    run = subprocess.run
    argv = ["git", "branch", "-D" if force else "-d", "topic"]

    def fail_deletion(command, **kwargs):
        if command == argv:
            if failure == "os_error":
                raise OSError("synthetic deletion failure")
            return subprocess.CompletedProcess(command, 1, "", "synthetic deletion failure")
        return run(command, **kwargs)

    with patch("subprocess.run", side_effect=fail_deletion):
        result = delete(force=force)
    assert result.status == "action_failed"
    assert result.raw["argv"] == argv
    assert "synthetic deletion failure" in result.raw["stderr"]
    assert result.diagnostics[0].code == "action.git.command_failed"
    assert exists(git)


@pytest.mark.parametrize("inputs", ({}, {"force": False}, {"force": True}))
def test_run_materializes_optional_force(repo, inputs):
    _, git = repo
    git("branch", "topic")
    result = execute_workflow(workflow(**inputs), connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.status == RuntimeStatus.OK
    assert not exists(git)


@pytest.mark.parametrize("force", (False, True, "invalid"))
@pytest.mark.parametrize("mode", (check_workflow, review_workflow, plan_workflow, assess_workflow_readiness), ids=("check", "review", "plan", "explain"))
def test_analysis_does_not_execute_deletion_or_validate_action_values(repo, mode, force):
    _, git = repo
    git("branch", "topic")
    with patch("subprocess.run", side_effect=AssertionError("Analysis must not execute the action")):
        result = mode(workflow(force=force), connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.status == RuntimeStatus.OK
    assert exists(git)


def test_next_uses_non_mutating_readiness(repo, capsys):
    root, git = repo
    git("branch", "topic")
    target = workflow(force=True)
    entry = SimpleNamespace(
        playbook_path=root / ".ordo" / "ordo.yaml", workflow_name=target.workflow,
        workflow_description="Delete disposable branch", workflow_category="test",
        workflow_when="After cleanup eligibility is established", working_directory=root,
    )
    activated = SimpleNamespace(
        playbook_path=entry.playbook_path, workflow_name=target.workflow, workflow=target,
        profile=None, working_directory=root, available_profiles=None,
        profile_working_directories=None, diagnostics=(),
    )
    with (
        patch("sys.argv", ["ordo-playbook", "next", "--json"]),
        patch("ordo.cli.list_playbook_workflows", return_value=(entry,)),
        patch("ordo.cli.inspect_playbook_workflow", return_value=entry),
        patch("ordo.cli.activate_playbook", return_value=activated),
        patch("subprocess.run", side_effect=AssertionError("Next must not delete branches")),
    ):
        assert cli_main() == 0
    assert json.loads(capsys.readouterr().out)["best_candidate"]["allowed"] is True
    assert exists(git)
