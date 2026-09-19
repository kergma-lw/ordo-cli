"""Remote observation parity over standalone help YAML, with no live IO."""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ordo.cli import main as cli_main
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.help_snippets import _git_remote_workflow
from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.runtime import (
    assess_workflow_readiness, check_workflow, execute_workflow, load_workflow_text,
    plan_workflow, review_workflow, validate_workflow_text,
)
from ordo.runtime.graphing import build_static_graph
from ordo.runtime.help_snippet_runner import normalized_fixture_provider


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Remote mode verification attempted live execution")
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
        workflow_description="Observe configured origin", workflow_category="inspect",
        workflow_when="Inspect local remote configuration", working_directory=tmp_path,
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


@pytest.mark.parametrize("mode", ("check", "review", "plan", "run", "explain", "next"))
@pytest.mark.parametrize("case", ("exists", "missing", "mirror", "literal-urls", "empty-lists", "probe-failed"))
def test_modes_preserve_remote_facts_and_workflow_guard(mode, case, tmp_path, capsys):
    world = describe_help_snippet_worlds()["git-remote-" + ("missing" if case == "missing" else "exists")]
    fixture = world["probes"]["git.remote"][0]
    if case == "mirror":
        fixture["outputs"]["mirror"] = True
    if case == "literal-urls":
        fixture["outputs"].update(fetch_urls=["x::literal\r", "x::literal\r"],
                                  push_urls=[" ssh://example.com/Repo.git ", "a\u2028b"])
    if case == "empty-lists":
        fixture["outputs"].update(fetch_urls=[], push_urls=[])
    if case == "probe-failed":
        fixture.update(status="probe_failed", outputs={})
    calls = []
    provider = normalized_fixture_provider(world, references={"git.remote"}, calls=calls,
                                           call_budget=12, strict_nulls=True)
    source = _git_remote_workflow()
    assert validate_workflow_text(source).status.value == "ok"
    workflow = replace(load_workflow_text(source), inputs=world["inputs"], explicit_input_keys=tuple(world["inputs"]))
    result, next_payload = invoke(mode, workflow, provider, tmp_path, capsys)
    success = case not in {"missing", "probe-failed"}
    assert calls and len(calls) <= 12
    assert all(call["reference"] == "git.remote" and call["inputs"] == {"remote": "origin"} for call in calls)
    assert {call["phase"] for call in calls} <= ({"probe", "execute"} if mode == "run" else {"probe"})
    if mode == "run":
        assert result.status.value == ("ok" if success else "execution_error"), result.to_contract()
        if case == "probe-failed":
            assert not result.published
            assert result.failed_step == "observe-remote"
        else:
            if case == "missing":
                assert result.failed_step == "require-existing-remote"
                assert not result.published
                assert result.outputs["executed_steps"] == ["observe-remote"]
                assert result.outputs["skipped_steps"] == [
                    "publish-remote-facts", "count-fetch-urls", "count-push-urls", "publish-url-counts",
                ]
                assert result.operation_results[-1].outputs == fixture["outputs"]
            else:
                assert result.published[0] == fixture["outputs"]
                assert result.published[1] == {"fetch_count": len(fixture["outputs"]["fetch_urls"]),
                                               "push_count": len(fixture["outputs"]["push_urls"])}
    else:
        snapshot = result.outputs["check_snapshot"] if mode == "review" else result.outputs
        assert (snapshot["allowed_state"] == "allowed") is success
        assert snapshot["analysis_complete"] is (case != "probe-failed")
        assert not result.published
        if case != "probe-failed":
            observed = next(item for item in result.analysis_tree.preflight_step_items if item["name"] == "observe-remote")
            assert observed["preflight_classification"] == "read_only_analyzable"
            assert observed["outputs"] == fixture["outputs"]
        if mode in {"plan", "explain", "next"}:
            probe, = [item for item in result.outputs["step_items"] if item.get("reference") == "git.remote"]
            assert probe["kind"] == "probe" and probe["effect"] == "read_only"
    if next_payload is not None:
        assert next_payload["best_candidate"]["allowed"] is success
        assert next_payload["ready_now_available"] is success


def test_static_graph_nonimpact_without_observation():
    operation = get_public_connector_registry().get_operation("git.remote")
    assert operation.kind == "probe"
    assert not operation.effects
    assert not operation.invalidates_observations
    assert operation.inputs == {"remote": "string"}
    assert operation.outputs == {"name": "string", "exists": "boolean", "fetch_urls": ["string"],
                                 "push_urls": ["string"], "mirror": "boolean | null"}
    workflow = load_workflow_text(_git_remote_workflow())
    graph = build_static_graph(((workflow.workflow, workflow, "/snippet-world"),))
    assert graph["links"] == []
    assert graph["structural_links"] == []
    assert graph["possible_loop_components"] == []
