"""Actions primitive parity over exact help sources, never lifecycle YAML."""

import json
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ordo.cli import main as cli_main
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.help_snippets import _gh_actions_workflow
from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.runtime import (
    assess_workflow_readiness, check_workflow, execute_workflow, load_workflow_text,
    plan_workflow, review_workflow, validate_workflow_text,
)
from ordo.runtime.graphing import build_static_graph
from ordo.runtime.help_snippet_runner import normalized_fixture_provider


MODES = ("check", "review", "plan", "run", "explain", "next")
REFERENCES = {"gh.pr.checks", "gh.actions.run", "gh.actions.run.jobs"}


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Actions mode verification attempted live execution")
    for name in ("subprocess.run", "subprocess.Popen", "socket.create_connection",
                 "ordo.connectors.operations.evaluate_probe", "ordo.connectors.operations.execute_operation",
                 "ordo.runtime.providers.get_default_connector_provider"):
        monkeypatch.setattr(name, forbidden)


def invoke(mode, workflow, provider, tmp_path, capsys):
    functions = dict(check=check_workflow, review=review_workflow, plan=plan_workflow,
                     run=execute_workflow, explain=assess_workflow_readiness)
    if mode != "next":
        return functions[mode](workflow, connector_provider=provider), None
    entry = SimpleNamespace(
        playbook_path=tmp_path / "ordo.yaml", workflow_name=workflow.workflow,
        workflow_description="Observe Actions", workflow_category="inspect",
        workflow_when="Inspect a pinned attempt", working_directory=tmp_path,
        workflow_contract=workflow,
    )
    activated = SimpleNamespace(workflow=workflow, profile=None, working_directory=tmp_path, diagnostics=())
    results = []

    def explain(actual, **kwargs):
        result = assess_workflow_readiness(actual, connector_provider=provider, **kwargs)
        results.append(result)
        return result

    with (
        patch("sys.argv", ["ordo-playbook", "next", "--json"]),
        patch("ordo.cli.list_playbook_workflows", return_value=(entry,)),
        patch("ordo.cli.inspect_playbook_workflow", return_value=entry),
        patch("ordo.cli.activate_playbook", return_value=activated),
        patch("ordo.cli.assess_workflow_readiness", side_effect=explain),
    ):
        assert cli_main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    result, = results
    return result, json.loads(captured.out)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("case", ("direct", "bridge", "null-suite", "no-run", "empty-jobs", "failed-job", "incomplete-checks", "incomplete-jobs", "unselected-suite", "run-failure", "jobs-failure"))
def test_modes_observe_registered_handoff_and_authored_gates(mode, case, tmp_path, capsys):
    world_case = case if case in {"direct", "bridge", "null-suite", "no-run"} else "bridge"
    world = deepcopy(describe_help_snippet_worlds()["gh-actions-" + world_case])
    probes = world["probes"]
    if case == "empty-jobs":
        probes["gh.actions.run.jobs"][0]["outputs"].update(items=[], count=0)
    if case == "failed-job":
        probes["gh.actions.run.jobs"][0]["outputs"]["items"][0]["conclusion"] = "failure"
    if case.startswith("incomplete-"):
        reference = "gh.pr.checks" if case == "incomplete-checks" else "gh.actions.run.jobs"
        probes[reference][0]["outputs"]["complete"] = False
    if case == "unselected-suite":
        for check in probes["gh.pr.checks"][0]["outputs"]["checks"]:
            check["check_suite_id"] = None
    if case.endswith("-failure"):
        reference = "gh.actions.run" if case == "run-failure" else "gh.actions.run.jobs"
        probes[reference][0].update(status="actions_run_unavailable" if case == "run-failure" else "actions_jobs_unavailable", outputs={})
    calls = []
    provider = normalized_fixture_provider(world, references=REFERENCES, calls=calls, call_budget=20)
    source = _gh_actions_workflow(bridge=world_case != "direct")
    assert validate_workflow_text(source).status.value == "ok"
    workflow = replace(load_workflow_text(source), inputs=world["inputs"], explicit_input_keys=tuple(world["inputs"]))
    result, next_payload = invoke(mode, workflow, provider, tmp_path, capsys)
    success = case in {"direct", "bridge", "empty-jobs", "failed-job"}
    assert calls and len(calls) <= 20
    assert {call["phase"] for call in calls} <= ({"probe", "execute"} if mode == "run" else {"probe"})
    if case in {"null-suite", "unselected-suite", "incomplete-checks"}:
        assert {call["reference"] for call in calls} == {"gh.pr.checks"}
    if case in {"no-run", "run-failure"}:
        assert all(call["reference"] != "gh.actions.run.jobs" for call in calls)
    for call in calls:
        if call["reference"] == "gh.actions.run.jobs":
            assert call["inputs"] == {"repository": "acme/mobile-app", "run_id": 900, "attempt": 3}
    if mode == "run":
        assert result.status.value == ("ok" if success else "execution_error"), result.to_contract()
        if success:
            published, = result.published
            assert published["items"] == probes["gh.actions.run.jobs"][0]["outputs"]["items"]
            assert published["count"] == (0 if case == "empty-jobs" else 2)
            assert published["run_attempt"] == 3 and published["complete"] is True
        else:
            assert not result.published
            expected_step = {"null-suite": "require-suite-selector", "no-run": "require-found-run",
                             "incomplete-checks": "require-complete-checks", "incomplete-jobs": "require-complete-jobs",
                             "unselected-suite": "require-selected-suite", "run-failure": "observe-run", "jobs-failure": "observe-pinned-jobs"}[case]
            assert result.failed_step == expected_step
    else:
        snapshot = result.outputs["check_snapshot"] if mode == "review" else result.outputs
        assert (snapshot["allowed_state"] == "allowed") is success
        assert snapshot["analysis_complete"] is (not case.endswith("-failure"))
        assert not result.published
        if success:
            observed = next(item for item in result.analysis_tree.preflight_step_items if item["name"] == "observe-pinned-jobs")
            assert observed["preflight_classification"] == "read_only_analyzable"
            assert observed["outputs"]["run_attempt"] == 3
        if mode in {"plan", "explain", "next"}:
            probes_in_plan = [item for item in result.outputs["step_items"] if item.get("reference") in REFERENCES]
            assert {item["reference"] for item in probes_in_plan} == (REFERENCES - {"gh.pr.checks"} if case == "direct" else REFERENCES)
            assert all(item["kind"] == "probe" and item["effect"] == "read_only" for item in probes_in_plan)
    if next_payload is not None:
        assert next_payload["best_candidate"]["allowed"] is success
        assert next_payload["ready_now_available"] is success


def test_static_graph_nonimpact_uses_public_metadata_without_observation():
    registry = get_public_connector_registry()
    for reference in REFERENCES:
        operation = registry.get_operation(reference)
        assert operation.kind == "probe"
        assert not operation.effects
        assert not operation.invalidates_observations
    workflow = load_workflow_text(_gh_actions_workflow(bridge=True))
    graph = build_static_graph(((workflow.workflow, workflow, "/snippet-world"),))
    assert graph["links"] == []
    assert graph["structural_links"] == []
    assert graph["possible_loop_components"] == []
