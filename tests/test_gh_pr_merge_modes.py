"""Async merge mode parity using the public registry and fixture-only execution."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ordo.cli import main as cli_main
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import check_workflow, execute_workflow, assess_workflow_readiness, plan_workflow, review_workflow
from ordo.runtime.providers import ConnectorProvider
from ordo.runtime.resolution import ResolvedExpressionProbe
from ordo.runtime.value_resolution import resolve_runtime_value


MODES = ("check", "review", "plan", "explain", "next", "run")
READ_MODES = MODES[:-1]
SHA = "a" * 40
UUID = "12345678-1234-1234-1234-123456789abc"
TARGET = {"repository": "owner/repo", "pull_number": 42}
MERGE_INPUTS = {**TARGET, "merge_method": "squash", "expected_head_sha": SHA}
STACK_GATE = 'step.pr.outputs.stack_state == "standalone"'
HEAD_GUARD = f'gh.pr(repository="owner/repo", pull_number=42).head_sha == "{SHA}"'
REQUEST_PROBE = f'gh.pr.merge.request(repository="owner/repo", pull_number=42, request_id="{UUID}")'


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Mode parity attempted live connector execution")

    for name in (
        "subprocess.run", "subprocess.Popen",
        "ordo.connectors.operations.evaluate_probe",
        "ordo.connectors.operations.execute_operation",
        "ordo.runtime.providers.get_default_connector_provider",
    ):
        monkeypatch.setattr(name, forbidden)


@pytest.fixture
def fixture_provider():
    observations = {
        "gh.pr": {"stack_state": "standalone", "head_sha": SHA},
        "gh.pr.merge.request": {"request_id": UUID, "state": "pending", "merged": False},
    }
    calls = []

    def probe(resolved, _workflow):
        assert resolved.reference in observations
        expected = TARGET if resolved.reference == "gh.pr" else {**TARGET, "request_id": UUID}
        if isinstance(resolved, ResolvedExpressionProbe):
            inputs = {name: node.value for name, node in resolved.arguments}
        else:
            inputs = resolved.resolved_inputs
            if inputs is None:
                inputs = resolve_runtime_value(resolved.declared_with, _workflow)
        assert inputs == expected
        calls.append((resolved.reference, deepcopy(inputs)))
        return OperationResult(status="ok", outputs=deepcopy(observations[resolved.reference]))

    def execute(resolved, workflow):
        if resolved.reference != "gh.pr.merge":
            return probe(resolved, workflow)
        assert resolved.resolved_inputs == MERGE_INPUTS
        calls.append((resolved.reference, deepcopy(resolved.resolved_inputs)))
        return OperationResult(status="ok", outputs={
            "submission": "accepted", "request_id": UUID, "state": "pending", "merged": False,
        })

    provider = ConnectorProvider(
        registry=get_public_connector_registry(),
        guard_probe=Mock(side_effect=probe),
        step_executor=Mock(side_effect=execute),
    )
    return SimpleNamespace(provider=provider, observations=observations, calls=calls)


def merge_workflow(*, post_guard=False):
    blocks = (
        StepBlock(steps=(Step(name="observe-pr", operation=OperationRef("gh.pr", with_=TARGET), register="pr"),)),
        GuardBlock(guards=(Guard(expr=HEAD_GUARD),)),
        StepBlock(steps=(
            Step(name="admit-stack", gate=STACK_GATE),
            Step(name="merge", operation=OperationRef("gh.pr.merge", with_=MERGE_INPUTS),
                 register="merge"),
            Step(name="observe-request", operation=OperationRef("gh.pr.merge.request", with_={
                **TARGET, "request_id": "${step.merge.outputs.request_id}",
            }), register="request"),
            Step(name="publish-request", publish={
                "request_id": "${step.merge.outputs.request_id}",
                "request_state": "${step.request.outputs.state}",
                "merged": "${step.request.outputs.merged}",
            }),
        )),
    )
    if post_guard:
        blocks += (GuardBlock(guards=(Guard(expr=f'{REQUEST_PROBE}.state == "pending"'),)),)
    return Workflow(version=0, workflow="merge-mode-parity", blocks=blocks)


def invoke(mode, workflow, fixture, tmp_path, capsys):
    if mode != "next":
        function = dict(check=check_workflow, review=review_workflow, plan=plan_workflow,
                        explain=assess_workflow_readiness, run=execute_workflow)[mode]
        return function(workflow, connector_provider=fixture.provider), None

    entry = SimpleNamespace(
        playbook_path=tmp_path / "ordo.yaml", workflow_name=workflow.workflow,
        workflow_description="Submit a pinned async merge", workflow_category="change",
        workflow_when="Merge an admitted PR", working_directory=tmp_path,
        workflow_contract=workflow,
    )
    activated = SimpleNamespace(workflow=workflow, profile=None, working_directory=tmp_path, diagnostics=())
    results = []

    def explain(actual_workflow, **kwargs):
        result = assess_workflow_readiness(actual_workflow, connector_provider=fixture.provider, **kwargs)
        results.append(result)
        return result

    with (
        patch("sys.argv", ["ordo-playbook", "next", "--json"]),
        patch("ordo.cli.list_playbook_workflows", return_value=(entry,)),
        patch("ordo.cli.inspect_playbook_workflow", return_value=entry),
        patch("ordo.cli.activate_playbook", return_value=activated),
        patch("ordo.cli.assess_workflow_readiness", side_effect=explain) as explained,
    ):
        assert cli_main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    explained.assert_called_once()
    result, = results
    return result, json.loads(captured.out)


def verdict(mode, result):
    return result.outputs["check_snapshot"] if mode == "review" else result.outputs


@pytest.mark.parametrize("mode", READ_MODES)
@pytest.mark.parametrize("post_guard", (False, True), ids=("ready-frontier", "deferred-guard"))
def test_read_modes_defer_merge_outcomes(mode, post_guard, fixture_provider, tmp_path, capsys):
    result, next_payload = invoke(mode, merge_workflow(post_guard=post_guard), fixture_provider, tmp_path, capsys)

    assert result.status == RuntimeStatus.OK, result.to_contract()
    fixture_provider.provider.step_executor.assert_not_called()
    assert {reference for reference, _ in fixture_provider.calls} == {"gh.pr"}
    assert not result.published
    assert not any(item.level == "error" for item in result.diagnostics)
    snapshot = verdict(mode, result)
    assert snapshot["allowed_state"] == ("unknown" if post_guard else "allowed")
    assert snapshot["analysis_complete"] is (not post_guard)
    items = result.analysis_tree.preflight_step_items
    merge = next(item for item in items if item["name"] == "merge")
    assert merge["status"] == "halted"
    assert merge["action_call"] == {"reference": "gh.pr.merge", "with": MERGE_INPUTS}
    if mode != "review":
        assert result.outputs["preflight_halts"][0]["reason"] == "effectful_step_encountered"
        assert "merge" not in result.outputs["preflight_registers"]
        assert "request" not in result.outputs["preflight_registers"]
    if post_guard:
        assert "effectful_step_encountered" in snapshot["incomplete_reasons"]
    if mode in ("plan", "explain", "next"):
        steps = {item["name"]: item for item in result.outputs["step_items"]}
        assert steps["merge"]["effect"] == "effectful"
        assert steps["observe-request"]["kind"] == "probe"
        assert result.outputs["execution_allowed"] is (not post_guard)
    if next_payload is not None:
        assert next_payload["best_candidate"]["allowed"] is (not post_guard)
        assert next_payload["ready_now_available"] is (not post_guard)


def test_run_submits_only_to_fixture_and_hands_off_request_id(fixture_provider, tmp_path, capsys):
    result, _ = invoke("run", merge_workflow(post_guard=True), fixture_provider, tmp_path, capsys)

    assert result.status == RuntimeStatus.OK, result.to_contract()
    assert [inputs for reference, inputs in fixture_provider.calls if reference == "gh.pr.merge"] == [MERGE_INPUTS]
    requests = [inputs for reference, inputs in fixture_provider.calls if reference == "gh.pr.merge.request"]
    assert requests and all(inputs == {**TARGET, "request_id": UUID} for inputs in requests)
    assert result.published == ({"request_id": UUID, "request_state": "pending", "merged": False},)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("field,value", (
    ("stack_state", "stacked"), ("stack_state", "unknown"), ("stack_state", None),
    ("head_sha", "b" * 40),
))
def test_observed_stack_gate_and_head_guard_block_merge(mode, field, value, fixture_provider, tmp_path, capsys):
    fixture_provider.observations["gh.pr"][field] = value
    result, next_payload = invoke(mode, merge_workflow(), fixture_provider, tmp_path, capsys)

    assert not any(reference == "gh.pr.merge" for reference, _ in fixture_provider.calls)
    assert not any(reference == "gh.pr.merge.request" for reference, _ in fixture_provider.calls)
    assert not result.published
    if mode == "run" and field == "stack_state":
        assert result.status == RuntimeStatus.EXECUTION_ERROR
        assert result.failed_step == "admit-stack"
        diagnostic = next(item for item in result.diagnostics if item.code == "runtime.step.gate.failed")
        assert STACK_GATE in diagnostic.message
    else:
        assert verdict(mode, result)["allowed_state"] == "blocked"
    if field == "head_sha":
        assert result.status == (RuntimeStatus.OK if mode == "review" else RuntimeStatus.GUARD_FAILED)
        # A successfully observed false predicate is a guard failure, not a
        # connector error: the evidence lives in the failed guard/result.
        assert not any(item.level == "error" for item in result.diagnostics)
        assert result.failed_guard == HEAD_GUARD
    elif mode != "run":
        assert result.status == RuntimeStatus.OK
        merge = next(item for item in result.analysis_tree.preflight_step_items if item["name"] == "admit-stack")
        assert merge["status"] == "gate_blocked"
        assert [item["expression"] for item in merge["gate_report"]["failed"]] == [STACK_GATE]
    if mode in READ_MODES:
        fixture_provider.provider.step_executor.assert_not_called()
    if next_payload is not None:
        assert next_payload["best_candidate"]["allowed"] is False
        assert next_payload["ready_now_available"] is False
        assert next_payload["best_candidate"]["blockers"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("state", ("pending", "merged", "failed", "enqueued"))
def test_registered_request_probe_is_readable_without_submitting_merge(mode, state, fixture_provider, tmp_path, capsys):
    fixture_provider.observations["gh.pr.merge.request"].update(state=state, merged=state == "merged")
    workflow = Workflow(version=0, workflow="observe-saved-merge-request", blocks=(
        StepBlock(steps=(Step(name="observe-request", operation=OperationRef(
            "gh.pr.merge.request", with_={**TARGET, "request_id": UUID}), register="request"),)),
        GuardBlock(guards=(Guard(expr=f'{REQUEST_PROBE}.state == "{state}"'),)),
    ))
    result, next_payload = invoke(mode, workflow, fixture_provider, tmp_path, capsys)

    assert result.status == RuntimeStatus.OK, result.to_contract()
    assert fixture_provider.calls
    assert {reference for reference, _ in fixture_provider.calls} == {"gh.pr.merge.request"}
    assert not any(item.level == "error" for item in result.diagnostics)
    if mode != "run":
        assert verdict(mode, result)["allowed_state"] == "allowed"
        fixture_provider.provider.step_executor.assert_not_called()
        observed = result.analysis_tree.preflight_step_items[0]
        assert observed["status"] == "interpreted"
        assert observed["outputs"]["state"] == state
    if next_payload is not None:
        assert next_payload["best_candidate"]["allowed"] is True
def test_merge_invalidation_covers_pr_root_and_request_descendants():
    from connectors.gh.actions.pr.merge import info
    from ordo.runtime.checking import _scope_invalidated

    scopes = info().invalidates_observations
    for reference in ("gh.pr", "gh.pr.checks", "gh.pr.merge.request", "gh.issue", "gh.project.issue"):
        assert any(_scope_invalidated(reference, scope) for scope in scopes)
