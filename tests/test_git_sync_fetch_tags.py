import subprocess
from unittest.mock import patch

from ordo.connectors.registry import get_public_connector_registry
from ordo.connectors.operations import execute_action
from ordo.model.workflow import OperationRef, Step, Workflow
from ordo.runtime.resolution import ResolvedOperation


def invoke(remote="origin", result=None):
    workflow = Workflow(version=0, workflow="tags", guards=(), steps=(Step(name="fetch", operation=OperationRef("git.sync.fetch-tags", with_={"remote": remote})),))
    operation = get_public_connector_registry().get_operation("git.sync.fetch-tags")
    resolved = ResolvedOperation("git.sync.fetch-tags", "git", operation, "public")
    commands = [subprocess.CompletedProcess([], 0, "/tmp/repo\n", ""), subprocess.CompletedProcess([], 0, "origin\n", ""), result or subprocess.CompletedProcess([], 0, "", "")]
    with patch("subprocess.run", side_effect=commands) as run:
        outcome = execute_action(resolved, workflow)
    return outcome, [call.args[0] for call in run.call_args_list]


def test_fetch_tags_uses_only_explicit_tag_refspec():
    outcome, commands = invoke()
    assert outcome.status == "ok"
    assert outcome.outputs == {"remote": "origin", "fetched": True}
    assert commands[-1] == ["git", "fetch", "origin", "refs/tags/*:refs/tags/*"]


def test_fetch_tags_reports_tag_conflict_without_force():
    outcome, commands = invoke(result=subprocess.CompletedProcess([], 1, "", "! [rejected] v1 -> v1 (would clobber existing tag)"))
    assert outcome.status == "fetch_tags_blocked"
    assert "--force" not in commands[-1]
