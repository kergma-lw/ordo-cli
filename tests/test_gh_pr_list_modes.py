"""PR-list runtime parity through the public registry, with fixture-only I/O."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from connectors.gh.probes.pr import list as pr_list
from ordo.cli import main as cli_main
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.plugin_sdk import OperationContext, bootstrap_ok
from ordo.runtime import check_workflow, execute_workflow, assess_workflow_readiness, plan_workflow, review_workflow
from ordo.runtime.providers import ConnectorProvider
from ordo.runtime.resolution import ResolvedExpressionProbe
from ordo.runtime.value_resolution import resolve_runtime_value


MODES = ("check", "review", "plan", "run", "explain", "next")
INPUTS = {"repository": "owner/repo", "state": "all"}
LIST_PROBE = 'gh.pr.list(repository="owner/repo", state="all")'
LISTED_ITEMS = f"{LIST_PROBE}.items | length | ne(-1)"
ABSENCE = f"{LIST_PROBE}.count | eq(0)"
SELECT_ONE = "step.listed.outputs.count | eq(1)"
IDENTITY_FIELDS = ("head_repository", "head_owner", "head_ref", "base_repository", "base_ref")


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("PR-list parity attempted live connector execution")

    for name in (
        "subprocess.run", "subprocess.Popen", "socket.create_connection",
        "ordo.connectors.operations.evaluate_probe",
        "ordo.connectors.operations.execute_operation",
        "ordo.runtime.providers.get_default_connector_provider",
    ):
        monkeypatch.setattr(name, forbidden)


def pull(number):
    # Missing merged_at deliberately means unknown, even for a closed PR.
    return {
        "number": number, "state": "closed", "draft": False,
        "html_url": f"https://github.com/owner/repo/pull/{number}",
        "head": {"ref": "feature", "sha": "a" * 40, "repo": {"full_name": "fork/repo"}},
        "base": {"ref": "main", "sha": "b" * 40, "repo": {"full_name": "owner/repo"}},
    }


def expected_item(number):
    return {
        "number": number, "pull_ref": f"owner/repo#{number}",
        "url": f"https://github.com/owner/repo/pull/{number}",
        "state": "closed", "draft": False, "merged": None, "merged_at": None,
        "head_repository": "fork/repo", "head_repository_key": "fork/repo",
        "head_owner": "fork", "head_ref": "feature", "head_sha": "a" * 40,
        "base_repository": "owner/repo", "base_ref": "main", "base_sha": "b" * 40,
    }


@pytest.fixture
def fixture_provider():
    fixture = SimpleNamespace(nodes=[], fail_read=False, calls=[], outcomes=[], commands=[])

    def observe(resolved, workflow):
        assert resolved.reference == "gh.pr.list"
        assert resolved.operation.kind == "probe"
        if isinstance(resolved, ResolvedExpressionProbe):
            inputs = {name: node.value for name, node in resolved.arguments}
        else:
            inputs = resolved.resolved_inputs
            if inputs is None:
                inputs = resolve_runtime_value(resolved.declared_with, workflow)
        fixture.calls.append(deepcopy(inputs))
        header = "HTTP/2.0 200 OK\n"
        if fixture.fail_read:
            header += ('Link: <https://api.github.com/repos/owner/repo/pulls?'
                       'state=all&per_page=100&page=2>; rel="next"\n')
        response = SimpleNamespace(stdout=header + "\n" + json.dumps(fixture.nodes), raw={"page": 1})
        ctx = Mock(spec=OperationContext)
        ctx.reference = resolved.reference
        ctx.optional_input.side_effect = inputs.get
        ctx.bootstrap.return_value = bootstrap_ok(context={"repository": "owner/repo"})
        ctx.command.side_effect = [response, UnicodeError("fixture page two read failed")]
        fixture.commands.append(ctx.command)
        outcome = pr_list.run(ctx)
        fixture.outcomes.append(outcome)
        diagnostics = tuple(Diagnostic(code=item.code, level=item.level, message=item.message,
                                       details=item.details) for item in outcome.diagnostics)
        return OperationResult(status=outcome.status, summary=outcome.summary,
                               outputs=deepcopy(outcome.outputs), diagnostics=diagnostics, raw=outcome.raw)

    fixture.provider = ConnectorProvider(
        registry=get_public_connector_registry(),
        guard_probe=Mock(side_effect=observe), step_executor=Mock(side_effect=observe),
    )
    return fixture


def list_workflow(*, guard=LISTED_ITEMS, gate=None, inputs=None):
    steps = (Step(name="list-candidates", operation=OperationRef(
        "gh.pr.list", with_=INPUTS if inputs is None else inputs), register="listed"),)
    if gate is not None:
        steps += (Step(name="admit-selection", gate=gate),)
    blocks = (StepBlock(steps=steps),)
    if guard is not None:
        blocks += (GuardBlock(guards=(Guard(expr=guard),)),)
    blocks += (StepBlock(steps=(Step(name="publish-observation", publish={
        "items": "${step.listed.outputs.items}", "count": "${step.listed.outputs.count}",
    }),)),)
    return Workflow(version=0, workflow="list-mode-parity", blocks=blocks)


def invoke(mode, workflow, fixture, tmp_path, capsys):
    if mode != "next":
        function = dict(check=check_workflow, review=review_workflow, plan=plan_workflow,
                        run=execute_workflow, explain=assess_workflow_readiness)[mode]
        return function(workflow, connector_provider=fixture.provider), None

    entry = SimpleNamespace(
        playbook_path=tmp_path / "ordo.yaml", workflow_name=workflow.workflow,
        workflow_description="Observe pull request candidates", workflow_category="inspect",
        workflow_when="Inspect branch pull requests", working_directory=tmp_path,
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


def assert_probe_only(mode, fixture):
    assert fixture.calls
    assert all(inputs == INPUTS for inputs in fixture.calls)
    if mode == "run":
        fixture.provider.step_executor.assert_called_once()
        assert fixture.provider.step_executor.call_args.args[0].reference == "gh.pr.list"
    else:
        fixture.provider.step_executor.assert_not_called()


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("count", (0, 1, 3), ids=("zero", "one", "multiple"))
@pytest.mark.parametrize("with_guard", (True, False), ids=("listed-items-guard", "empty-guards"))
def test_complete_list_is_read_only_and_count_is_not_policy(mode, count, with_guard, fixture_provider, tmp_path, capsys):
    fixture_provider.nodes = [pull(n) for n in range(1, count + 1)]
    result, next_payload = invoke(mode, list_workflow(guard=LISTED_ITEMS if with_guard else None),
                                  fixture_provider, tmp_path, capsys)
    assert result.status == RuntimeStatus.OK, result.to_contract()
    assert not any(item.level == "error" for item in result.diagnostics)
    if with_guard or mode == "run":
        assert_probe_only(mode, fixture_provider)
    else:
        # No guards means read modes need no live evidence to establish
        # applicability; they do not execute a trailing observer/publication.
        assert not fixture_provider.calls
        fixture_provider.provider.step_executor.assert_not_called()
    expected = [expected_item(n) for n in range(1, count + 1)]
    for outcome in fixture_provider.outcomes:
        assert outcome.outputs == {**INPUTS, "head": None, "head_owner": None, "base": None,
                                   "items": expected, "count": count, "complete": True}
    if mode == "run":
        assert result.published == ({"items": expected, "count": count},)
    else:
        snapshot = verdict(mode, result)
        assert snapshot["allowed_state"] == "allowed"
        assert snapshot["analysis_complete"] is True
        assert not snapshot["incomplete_reasons"]
        if with_guard:
            observed = result.analysis_tree.preflight_step_items[0]
            assert observed["status"] == "interpreted"
            assert observed["preflight_classification"] == "read_only_analyzable"
            assert observed["outputs"]["items"] == expected
            assert all(item["merged"] is None for item in observed["outputs"]["items"])
        if mode != "review":
            assert not result.outputs["preflight_halts"]
    if mode in ("plan", "explain", "next"):
        observed = result.outputs["step_items"][0]
        assert observed["kind"] == "probe"
        assert observed["effect"] == "read_only"
        assert result.outputs["execution_allowed"] is True
    if next_payload is not None:
        assert next_payload["best_candidate"]["allowed"] is True
        assert next_payload["ready_now_available"] is True


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("count", (0, 1, 3), ids=("zero", "one", "multiple"))
def test_exactly_one_is_an_authored_gate_not_connector_failure(mode, count, fixture_provider, tmp_path, capsys):
    fixture_provider.nodes = [pull(n) for n in range(1, count + 1)]
    result, next_payload = invoke(mode, list_workflow(gate=SELECT_ONE), fixture_provider, tmp_path, capsys)
    assert_probe_only(mode, fixture_provider)
    assert all(outcome.status == "ok" for outcome in fixture_provider.outcomes)
    if count == 1:
        assert result.status == RuntimeStatus.OK, result.to_contract()
        if mode != "run":
            assert verdict(mode, result)["allowed_state"] == "allowed"
    else:
        assert_gate_blocked(mode, result, SELECT_ONE)
    if next_payload is not None:
        assert next_payload["best_candidate"]["allowed"] is (count == 1)
        assert next_payload["ready_now_available"] is (count == 1)


def assert_gate_blocked(mode, result, expression):
    assert not result.published
    if mode == "run":
        assert result.status == RuntimeStatus.EXECUTION_ERROR
        assert result.failed_step == "admit-selection"
        diagnostic, = [item for item in result.diagnostics if item.level == "error"]
        assert diagnostic.code == "runtime.step.gate.failed"
        assert expression in diagnostic.message
    else:
        assert result.status == RuntimeStatus.OK, result.to_contract()
        assert verdict(mode, result)["allowed_state"] == "blocked"
        assert not any(item.level == "error" for item in result.diagnostics)
        gate = next(item for item in result.analysis_tree.preflight_step_items if item["name"] == "admit-selection")
        assert gate["status"] == "gate_blocked"
        assert [item["expression"] for item in gate["gate_report"]["failed"]] == [expression]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("field", IDENTITY_FIELDS)
def test_template_unknown_identity_gate_blocks_before_absence(mode, field, fixture_provider, tmp_path, capsys):
    node = pull(1)
    side, key = {"head_repository": ("head", "repo"), "head_owner": ("head", "repo"),
                 "head_ref": ("head", "ref"), "base_repository": ("base", "repo"),
                 "base_ref": ("base", "ref")}[field]
    node[side][key] = None
    fixture_provider.nodes = [node]
    # This is the null-identity predicate from the published template, before
    # any exact-source filtering could turn unknown identity into false absence.
    gate = f"step.listed.outputs.items | only({field}=null) | length | eq(0)"
    result, next_payload = invoke(mode, list_workflow(gate=gate, guard=ABSENCE), fixture_provider, tmp_path, capsys)
    assert_probe_only(mode, fixture_provider)
    assert all(outcome.status == "ok" and outcome.outputs["items"][0][field] is None
               for outcome in fixture_provider.outcomes)
    assert_gate_blocked(mode, result, gate)
    assert result.failed_guard is None
    if next_payload is not None:
        assert next_payload["best_candidate"]["allowed"] is False
        assert next_payload["ready_now_available"] is False


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("failure", ("read", "missing-state"))
def test_failed_probe_never_publishes_or_proves_absence(mode, failure, fixture_provider, tmp_path, capsys):
    fixture_provider.nodes = [pull(1)]
    fixture_provider.fail_read = failure == "read"
    inputs = INPUTS if failure == "read" else {"repository": "owner/repo"}
    result, next_payload = invoke(mode, list_workflow(inputs=inputs, guard=ABSENCE),
                                  fixture_provider, tmp_path, capsys)
    expected_status = "pull_list_unavailable" if failure == "read" else "input_error"
    expected_code = "probe.gh_pr_list.read_failed" if failure == "read" else "probe.gh_pr_list.invalid_state"
    assert fixture_provider.outcomes
    for outcome, command in zip(fixture_provider.outcomes, fixture_provider.commands):
        assert outcome.status == expected_status
        assert outcome.outputs == {}
        assert outcome.diagnostics[0].code == expected_code
        assert command.call_count == (2 if failure == "read" else 0)
    assert not result.published
    assert result.failed_guard is None
    assert any(item.code == expected_code and item.level == "error" for item in result.diagnostics)
    if mode == "run":
        assert result.status == RuntimeStatus.EXECUTION_ERROR
        assert result.failed_step == "list-candidates"
        fixture_provider.provider.step_executor.assert_called_once()
    else:
        fixture_provider.provider.step_executor.assert_not_called()
        assert verdict(mode, result)["allowed_state"] != "allowed"
        assert verdict(mode, result)["analysis_complete"] is False
        assert "read_only_step_failed" in verdict(mode, result)["incomplete_reasons"]
        assert not any(node.evaluated for node in result.preflight_decision.guard_nodes)
        observed = result.analysis_tree.preflight_step_items[0]
        assert "outputs" not in observed
    if next_payload is not None:
        assert next_payload["best_candidate"]["allowed"] is False
        assert next_payload["ready_now_available"] is False
