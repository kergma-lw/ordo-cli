"""Readiness API contracts using synthetic engine workflows and fixture-only I/O."""

from copy import deepcopy
from inspect import Parameter, signature
from types import SimpleNamespace
from unittest.mock import Mock, call, patch, sentinel

import pytest

import ordo
import ordo.cli as cli
import ordo.runtime as runtime
from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.playbook import PlaybookError
from ordo.runtime import assess_workflow_readiness
from ordo.runtime import explaining
from ordo.runtime.providers import ConnectorProvider
from tests.support import STANDARD_CONNECTOR_PROVIDER


@pytest.mark.parametrize("module", [ordo, runtime, explaining], ids=["ordo", "runtime", "defining-module"])
def test_readiness_export_replaces_old_api_without_alias(module):
    assert module.assess_workflow_readiness is assess_workflow_readiness
    with pytest.raises(AttributeError):
        getattr(module, "explain_workflow")
    if module is not explaining:
        assert "assess_workflow_readiness" in module.__all__
        assert "explain_workflow" not in module.__all__


@pytest.mark.parametrize("explicit", [False, True], ids=["defaults", "explicit-context"])
def test_readiness_signature_and_exact_plan_then_enrichment_forwarding(explicit, tmp_path):
    parameters = list(signature(assess_workflow_readiness).parameters.values())
    assert [(p.name, p.kind, p.default) for p in parameters] == [
        ("workflow", Parameter.POSITIONAL_OR_KEYWORD, Parameter.empty),
        *[(name, Parameter.KEYWORD_ONLY, None) for name in (
            "profile", "available_profiles", "profile_working_directories",
            "guard_probe", "connector_provider",
        )],
    ]
    workflow = Workflow(version=0, workflow="forwarding")
    profile = Profile(name="fixture")
    context = {
        "profile": profile,
        "available_profiles": {"fixture": profile},
        "profile_working_directories": {"fixture": tmp_path, "unset": None},
        "guard_probe": Mock(),
        "connector_provider": STANDARD_CONNECTOR_PROVIDER,
    } if explicit else {p.name: None for p in parameters[1:]}
    calls = Mock()
    with (
        patch.object(explaining, "plan_workflow", return_value=sentinel.plan) as plan,
        patch.object(explaining, "explain_runtime_result", return_value=sentinel.enriched) as enrich,
    ):
        calls.attach_mock(plan, "plan")
        calls.attach_mock(enrich, "enrich")
        result = assess_workflow_readiness(workflow, **(context if explicit else {}))
    assert result is sentinel.enriched
    assert calls.mock_calls == [call.plan(workflow, **context), call.enrich(sentinel.plan)]
    assert plan.call_args.args[0] is workflow
    for name, value in context.items():
        assert plan.call_args.kwargs[name] is value


@pytest.mark.parametrize("state,category,action", [
    ("allowed", "ok", "execute_workflow"),
    ("blocked", "guard", "resolve_blocking_guards"),
    ("unknown", "incomplete", "complete_preflight_analysis"),
])
def test_readiness_enriches_one_observation_without_executing(state, category, action):
    mutate = Step(name="mutate", operation=OperationRef("shell.command", with_={"command": "never executed"}))
    # Guards observe connector facts directly; registered step outputs are not
    # valid guard roots. A later guard keeps the effect barrier incomplete.
    guard = GuardBlock(guards=(Guard(expr='git.branch.value != "main"'),))
    blocks = (guard, StepBlock(steps=(mutate,)))
    if state == "unknown":
        blocks += (GuardBlock(guards=(Guard(expr="true"),)),)
    workflow = Workflow(version=0, workflow="readiness", blocks=blocks)
    observation = OperationResult(status="ok", outputs={"value": "main" if state == "blocked" else "feature/demo"})
    probe = Mock(return_value=observation)
    executor = Mock(side_effect=AssertionError("readiness executed a business step"))
    provider = ConnectorProvider(
        registry=STANDARD_CONNECTOR_PROVIDER.registry, guard_probe=probe, step_executor=executor,
    )
    plans = []
    snapshots = []

    def capture_plan(*args, **kwargs):
        planned = runtime.plan_workflow(*args, **kwargs)
        plans.append(planned)
        snapshots.append(deepcopy(planned.to_contract()))
        return planned

    with (
        patch.object(explaining, "plan_workflow", side_effect=capture_plan) as plan,
        patch.object(explaining, "explain_runtime_result", wraps=explaining.explain_runtime_result) as enrich,
    ):
        result = assess_workflow_readiness(workflow, connector_provider=provider)

    plan.assert_called_once()
    planned, = plans
    enrich.assert_called_once_with(planned)
    assert result.status is (RuntimeStatus.GUARD_FAILED if state == "blocked" else RuntimeStatus.OK), result.diagnostics
    probe.assert_called_once()
    assert probe.call_args.args[0].reference == "git.branch"
    executor.assert_not_called()
    assert planned.to_contract() == snapshots[0]
    assert result.mode is Mode.EXPLAIN
    assert result.status is planned.status
    for name in ("plan", "analysis_tree", "preflight_decision", "failed_guard", "failed_step", "operation_results", "diagnostics"):
        assert getattr(result, name) == getattr(planned, name)
    assert result.analysis_tree is planned.analysis_tree
    assert result.preflight_decision is planned.preflight_decision
    assert result.outputs is not planned.outputs
    assert {key: result.outputs[key] for key in planned.outputs} == planned.outputs
    assert set(result.outputs) - set(planned.outputs) == {"explanation", "reason_category", "next_actions"}
    assert result.outputs["allowed_state"] == state
    assert result.outputs["analysis_complete"] is (state != "unknown")
    assert result.outputs["explanation"]["allowed"] is (state == "allowed")
    assert result.outputs["reason_category"] == result.outputs["explanation"]["category"] == category
    assert result.outputs["next_actions"][0]["action"] == action


def test_cli_explain_dispatches_readiness_with_full_profile_context(tmp_path):
    workflow = Workflow(version=0, workflow="cli-readiness")
    profile = Profile(name="fixture")
    profiles = {"fixture": profile}
    directories = {"fixture": tmp_path}
    with patch.object(cli, "assess_workflow_readiness", return_value=sentinel.explanation) as assess:
        result = cli._run_mode("explain", workflow, profile, profiles, directories)
    assert result is sentinel.explanation
    assess.assert_called_once_with(
        workflow, profile=profile, available_profiles=profiles, profile_working_directories=directories,
    )


@pytest.mark.parametrize("relaxed", [False, True], ids=["normal-next", "relaxed-next"])
def test_next_assesses_activated_candidate_once(relaxed, tmp_path):
    workflow = runtime.load_workflow_text('''version: 0
workflow: candidate
inputs:
  command: {}
blocks:
  - steps:
      - name: mutate
        uses: shell.command
        with:
          command: ${inputs.command}
''')
    profile = Profile(name="fixture")
    activated = SimpleNamespace(
        workflow=workflow, profile=profile, working_directory=None, diagnostics=(),
        available_profiles={"fixture": profile}, profile_working_directories={"fixture": tmp_path},
    )
    entry = SimpleNamespace(
        workflow_name="candidate", workflow_description=None, workflow_category=None,
        workflow_when=None, working_directory=None, workflow_contract=workflow,
        playbook_path=tmp_path / "ordo.yaml",
    )
    missing = PlaybookError(diagnostics=(Diagnostic(
        code="playbook.workflow.input_missing", level="error", message="Missing command",
        details={"input": "command"},
    ),))
    result = RuntimeResult(mode=Mode.EXPLAIN, status=RuntimeStatus.OK)
    args = SimpleNamespace(playbook_file=entry.playbook_path, profile="fixture", mode="next", json=True)
    with (
        # Topology classification resolves operations through the default
        # provider, unlike readiness's explicit connector_provider parameter.
        patch("ordo.runtime.resolution.get_default_connector_provider", return_value=STANDARD_CONNECTOR_PROVIDER),
        patch.object(cli, "list_playbook_workflows", return_value=(entry,)),
        patch.object(cli, "inspect_playbook_workflow", return_value=entry),
        patch.object(cli, "activate_playbook", side_effect=[missing, activated] if relaxed else [activated]) as activate,
        patch.object(cli, "assess_workflow_readiness", return_value=result) as assess,
        patch.object(cli, "build_next_candidate", return_value=sentinel.candidate) as build,
        patch.object(cli, "rank_next_candidates", return_value=sentinel.ranked) as rank,
    ):
        payload = cli._build_next_payload(args, input_overrides={}, include_graph=False)
    assert payload is sentinel.ranked
    assert activate.call_count == (2 if relaxed else 1)
    assert activate.call_args.kwargs["input_overrides"] == (
        {"command": "__ordo_next_placeholder__command"} if relaxed else {}
    )
    assess.assert_called_once_with(
        workflow, profile=profile, available_profiles=activated.available_profiles,
        profile_working_directories=activated.profile_working_directories,
    )
    build.assert_called_once()
    assert build.call_args.kwargs["runtime_result"].diagnostics == (missing.diagnostics if relaxed else ())
    rank.assert_called_once_with(
        [sentinel.candidate], requested_profile="fixture", input_override_keys=[],
        playbook_path=str(entry.playbook_path), include_graph=False,
    )
