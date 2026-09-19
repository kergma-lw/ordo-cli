import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from connectors.fs.probes import file as probe
from ordo.cli import main as cli_main
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, Workflow
from ordo.runtime import check_workflow, execute_workflow, assess_workflow_readiness, plan_workflow, review_workflow
from tests.support import STANDARD_CONNECTOR_PROVIDER


SECURE_OPEN_UNAVAILABLE = "probe.fs_file.secure_open_unavailable"
FILE_GUARD = "fs.file(path=inputs.path).exists"


@pytest.fixture
def file_workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "file.txt"
    path.write_text("Readable content must not become an unsafe fallback.", encoding="utf-8")
    workflow = Workflow(
        version=0,
        workflow="fs-file-mode-safety",
        declared_inputs={"path": {}},
        inputs={"path": str(path)},
        blocks=(GuardBlock(guards=(Guard(expr=FILE_GUARD),)),),
    )
    forbidden_open = Mock(side_effect=AssertionError("Unexpected descriptor open"))
    monkeypatch.setattr(probe.os, "O_NOFOLLOW", None, raising=False)
    monkeypatch.setattr(probe.os, "open", forbidden_open)
    with patch("subprocess.run", side_effect=AssertionError("Unexpected subprocess")) as run:
        yield workflow
        forbidden_open.assert_not_called()
        run.assert_not_called()


@pytest.mark.parametrize("mode", (check_workflow, review_workflow, plan_workflow, assess_workflow_readiness, execute_workflow), ids=("check", "review", "plan", "explain", "run"))
def test_unavailable_secure_open_blocks_runtime_modes(mode, file_workflow):
    result = mode(file_workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    verdict = result.outputs["check_snapshot"] if mode is review_workflow else result.outputs

    assert verdict["allowed_state"] == "blocked"
    if mode is review_workflow:
        assert result.status == RuntimeStatus.OK
        assert verdict["status"] == "guard_failed"
    else:
        assert result.status == RuntimeStatus.GUARD_FAILED
        assert result.outputs["can_execute"] is False
    if mode in (plan_workflow, assess_workflow_readiness):
        assert result.outputs["execution_allowed"] is False
    if mode is assess_workflow_readiness:
        assert result.outputs["explanation"]["allowed"] is False
    if mode is execute_workflow:
        assert result.outputs["executed_steps"] == []
    assert any(diagnostic.code == SECURE_OPEN_UNAVAILABLE and diagnostic.level == "error" for diagnostic in result.diagnostics)


def test_next_retains_secure_open_diagnostic_without_recommending_execution(file_workflow, tmp_path, capsys):
    entry = SimpleNamespace(
        playbook_path=tmp_path / ".ordo" / "ordo.yaml",
        workflow_name=file_workflow.workflow,
        workflow_description="Inspect a regular file",
        workflow_category="inspect",
        workflow_when="Inspect file content",
        working_directory=tmp_path,
    )
    activated = SimpleNamespace(
        playbook_path=entry.playbook_path,
        workflow_name=file_workflow.workflow,
        workflow=file_workflow,
        profile=None,
        working_directory=tmp_path,
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
    activate.assert_called_once_with(workflow_name=file_workflow.workflow, profile_name=None, input_overrides={}, playbook_path=None)
    assert exit_code == 0, captured.err
    payload = json.loads(captured.out)
    assert payload["mode"] == "next"
    candidate, = payload["candidates"]
    assert candidate["workflow"] == file_workflow.workflow
    assert candidate["allowed"] is False
    assert candidate["candidate_class"] == "weak_match"
    assert candidate["blockers"] == [FILE_GUARD]
    assert any(diagnostic["code"] == SECURE_OPEN_UNAVAILABLE and diagnostic["level"] == "error" for diagnostic in candidate["diagnostics"])
    assert payload["best_candidate"]["allowed"] is False
    assert payload["ready_now_available"] is False
    assert payload["uncertainty"]["kind"] == "no_ready_now_candidate"
