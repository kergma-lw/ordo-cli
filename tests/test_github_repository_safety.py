import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from connectors.gh._repository import normalize_repository_value, resolve_repository_identity, split_repository
from ordo.cli import main as cli_main
from ordo.connectors.operations import evaluate_probe, execute_action
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.github_repository import normalize_github_repository
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import check_workflow, execute_workflow, assess_workflow_readiness, plan_workflow, review_workflow
from ordo.runtime.resolution import ResolvedOperation
from ordo.runtime.reviewing import _normalize_github_repository_value
from tests.support import STANDARD_CONNECTOR_PROVIDER


MALICIOUS = "owner/repo?x=y"
INVALID = "probe.gh_repo_actions_permissions.invalid_repository"
GUARD = "gh.repo.actions.permissions(repository=inputs.repository).enabled == true"


@pytest.mark.parametrize("value", (
    None, 7, "owner", "owner/repo/extra", "./repo", "owner/..", "../repo", "owner/.",
    "-owner/repo", "own%65r/repo", MALICIOUS, "owner/repo#fragment", "own?er/repo",
    "owner/repo\\extra", "own\u00e9r/repo", "owner/repo\n", "\towner/repo", "owner/re po",
    "owner/repo\x00", "\u00a0owner/repo", "owner/", "/repo",
))
def test_repository_grammar_rejects_unsafe_operands(value):
    assert normalize_github_repository(value) is None
    assert normalize_repository_value(value) is None
    assert split_repository(value) is None


@pytest.mark.parametrize("value", (
    " Owner_1/Repo.Name-2 ", "owner/.github", "owner/-demo", "owner/-",
    ".owner/repo", "owner/...", "a" * 300 + "/" + "R" * 300,
))
def test_repository_grammar_preserves_literal_operands(value):
    expected = value.strip(" ")
    assert normalize_github_repository(value) == expected
    assert normalize_repository_value(value) == expected
    assert split_repository(value) == tuple(expected.split("/"))


@pytest.mark.parametrize("value", (" Owner/.github ", MALICIOUS))
def test_review_uses_same_repository_grammar(value):
    assert _normalize_github_repository_value(value) == normalize_github_repository(value)


@pytest.fixture
def auth_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def command(argv, **kwargs):
        assert argv == ["gh", "auth", "status"], f"Unexpected repository request: {argv!r}"
        return subprocess.CompletedProcess(argv, 0, stdout="authenticated\n", stderr="")

    with patch("subprocess.run", side_effect=command) as run:
        yield run


@pytest.mark.parametrize("reference", (
    "gh.pr", "gh.pr.diff", "gh.pr.comments", "gh.pr.review_comments", "gh.pr.checks", "gh.pr.timeline",
    "gh.repo.actions.permissions", "gh.repo.actions.permissions.set",
))
def test_rest_handlers_reject_invalid_repository_before_any_api(reference, auth_only):
    action = reference.endswith(".set")
    inputs = {"repository": MALICIOUS}
    inputs.update({"enabled": False} if action else {"pull_number": 7} if reference.startswith("gh.pr") else {})
    operation_ref = OperationRef(reference, with_=inputs)
    workflow = Workflow(
        version=0, workflow="repository-safety", connector_contexts={"gh": {"repository": "context/repo"}},
        guards=() if action else (Guard(operation_ref),),
        steps=(Step(name="mutate", operation=operation_ref),) if action else (),
    )
    operation = get_public_connector_registry().get_operation(reference)
    assert operation is not None
    resolved = ResolvedOperation(reference, "gh", operation, "public")
    result = (execute_action if action else evaluate_probe)(resolved, workflow)
    assert result.status == ("set_blocked" if action else "probe_failed")
    prefix = "action" if action else "probe"
    diagnostic_name = "gh_pr.timeline" if reference == "gh.pr.timeline" else reference.replace(".", "_")
    assert [d.code for d in result.diagnostics] == [f"{prefix}.{diagnostic_name}.invalid_repository"]
    assert result.diagnostics[0].level == "error"
    auth_only.assert_called_once()


def test_invalid_context_is_rejected_before_auth(auth_only):
    operation = get_public_connector_registry().get_operation("gh.repo.actions.permissions")
    workflow = Workflow(
        version=0, workflow="repository-safety", connector_contexts={"gh": {"repository": MALICIOUS}},
        guards=(Guard(OperationRef("gh.repo.actions.permissions")),),
    )
    result = evaluate_probe(ResolvedOperation("gh.repo.actions.permissions", "gh", operation, "public"), workflow)
    assert result.status == "repository_invalid"
    assert [d.code for d in result.diagnostics] == ["bootstrap.gh_repository_invalid"]
    auth_only.assert_not_called()


def test_explicit_repository_is_not_limited_to_context():
    ctx = SimpleNamespace(
        reference="gh.repo", optional_input=lambda name: " Other/.github ",
        bootstrap=lambda: SimpleNamespace(context={"repository": "default/repo"}),
    )
    identity = resolve_repository_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_repo")
    assert (identity.repository, identity.owner, identity.repo) == ("Other/.github", "Other", ".github")
    assert [d.code for d in identity.diagnostics] == ["probe.gh_repo.repository_override"]
    assert identity.diagnostics[0].level == "warning"


def guarded_workflow():
    return Workflow(
        version=0, workflow="repository-safety", declared_inputs={"repository": {}}, inputs={"repository": MALICIOUS},
        blocks=(GuardBlock(guards=(Guard(expr=GUARD),)), StepBlock(steps=(
            Step(name="must-not-run", operation=OperationRef("gh.repo.actions.permissions.set", with_={"enabled": False})),
        ))),
    )


@pytest.mark.parametrize("mode", (check_workflow, review_workflow, plan_workflow, assess_workflow_readiness, execute_workflow),
                         ids=("check", "review", "plan", "explain", "run"))
def test_invalid_repository_blocks_runtime_modes(mode, auth_only):
    result = mode(guarded_workflow(), connector_provider=STANDARD_CONNECTOR_PROVIDER)
    verdict = result.outputs["check_snapshot"] if mode is review_workflow else result.outputs
    assert verdict["allowed_state"] == "blocked"
    if mode is review_workflow:
        assert result.status == RuntimeStatus.OK
        assert verdict["status"] == "guard_failed"
    else:
        assert result.status == RuntimeStatus.GUARD_FAILED
        assert result.outputs["can_execute"] is False
    if mode is execute_workflow:
        assert result.outputs["executed_steps"] == []
        assert "must-not-run" in result.outputs["skipped_steps"]
    assert any(d.code == INVALID and d.level == "error" for d in result.diagnostics)
    assert auth_only.called


def test_next_does_not_recommend_invalid_repository(tmp_path, auth_only, capsys):
    workflow = guarded_workflow()
    entry = SimpleNamespace(
        playbook_path=tmp_path / ".ordo" / "ordo.yaml", workflow_name=workflow.workflow,
        workflow_description="Inspect repository permissions", workflow_category="inspect",
        workflow_when="Inspect repository permissions", working_directory=tmp_path,
    )
    activated = SimpleNamespace(
        playbook_path=entry.playbook_path, workflow_name=workflow.workflow, workflow=workflow,
        profile=None, working_directory=tmp_path, available_profiles=None,
        profile_working_directories=None, diagnostics=(),
    )
    with (
        patch("sys.argv", ["ordo-playbook", "next", "--json"]),
        patch("ordo.cli.list_playbook_workflows", return_value=(entry,)),
        patch("ordo.cli.inspect_playbook_workflow", return_value=entry),
        patch("ordo.cli.activate_playbook", return_value=activated),
    ):
        exit_code = cli_main()
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    payload = json.loads(captured.out)
    candidate = next(item for item in payload["candidates"] if item["workflow"] == workflow.workflow)
    assert candidate["allowed"] is False
    assert candidate["candidate_class"] == "weak_match"
    assert candidate["blockers"] == [GUARD]
    assert any(d["code"] == INVALID and d["level"] == "error" for d in candidate["diagnostics"])
    assert payload["best_candidate"]["allowed"] is False
    assert payload["ready_now_available"] is False
    assert auth_only.called
