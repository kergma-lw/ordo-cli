"""Exact published Actions sources, normalized fixtures, and closed dispatch."""

from copy import deepcopy

import pytest

from ordo.model.help_snippets import GH_ACTIONS_TARGETS, describe_help_snippets
from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.runtime.help_snippet_runner import normalized_fixture_provider, verify_help_snippet


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Actions snippets attempted live execution")
    for name in ("subprocess.run", "subprocess.Popen", "socket.create_connection",
                 "ordo.connectors.operations.evaluate_probe", "ordo.connectors.operations.execute_operation",
                 "ordo.runtime.providers.get_default_connector_provider"):
        monkeypatch.setattr(name, forbidden)


def example(case="bridge", handle="connector.gh.actions.run"):
    return next(item for item in describe_help_snippets()[handle]["canonical_examples"]
                if item["name"] == "gh_actions_" + case.replace("-", "_"))


def verify(item, **kwargs):
    return verify_help_snippet(snippet=item["yaml"], **{
        key: item["verification"][key] for key in ("world", "target", "insertion_mode")}, **kwargs)


@pytest.mark.parametrize("handle", GH_ACTIONS_TARGETS)
@pytest.mark.parametrize("case", ("direct", "bridge", "null-suite", "no-run"))
def test_published_source_executes_verbatim(handle, case):
    item = example(case, handle)
    assert item["yaml"] == example(case)["yaml"]
    result = verify(item)
    assert result.workflow_text == item["yaml"]
    assert result.verification_path == "fixture_execution"
    assert result.status == item["verification"]["expected_status"], result.runtime_result.to_contract()
    assert len(result.calls) <= 20
    if case in {"null-suite", "no-run"}:
        assert not result.runtime_result.published
        assert all(call["reference"] != "gh.actions.run.jobs" for call in result.calls)
        assert result.runtime_result.failed_step == ("require-suite-selector" if case == "null-suite" else "require-found-run")
        if case == "null-suite":
            assert {call["reference"] for call in result.calls} == {"gh.pr.checks"}
    else:
        jobs = [call for call in result.calls if call["reference"] == "gh.actions.run.jobs"]
        assert jobs and all(call["inputs"] == {"repository": "acme/mobile-app", "run_id": 900, "attempt": 3} for call in jobs)
        published, = result.runtime_result.published
        assert published == {"run_id": 900, "run_attempt": 3, "items": result.effective_world["probes"]["gh.actions.run.jobs"][0]["outputs"]["items"], "count": 2, "complete": True}


@pytest.mark.parametrize("change", ("text", "target", "mode", "world"))
def test_source_admission_has_no_validation_or_live_fallback(change):
    item = example()
    args = dict(snippet=item["yaml"], world="gh-actions-bridge", target="connector.gh.actions.run", insertion_mode="workflow_fragment")
    args[{"text": "snippet", "target": "target", "mode": "insertion_mode", "world": "world"}[change]] = {
        "text": item["yaml"] + "\n", "target": "connector.shell.command", "mode": "step_fragment", "world": "gh-actions-unknown"}[change]
    with pytest.raises(ValueError):
        verify_help_snippet(**args)


@pytest.mark.parametrize("change", ("extra-input", "extra-output", "missing-output", "nested-output", "bool-id", "missing-fixture", "unexpected-operation", "binding"))
def test_strict_normalized_fixtures(change):
    world = deepcopy(describe_help_snippet_worlds()["gh-actions-bridge"])
    fixture = world["probes"]["gh.actions.run.jobs"][0]
    if change == "extra-input":
        fixture["with_"]["latest"] = True
    elif change == "extra-output":
        fixture["outputs"]["tested_sha"] = "a" * 40
    elif change == "missing-output":
        del fixture["outputs"]["complete"]
    elif change == "nested-output":
        fixture["outputs"]["items"][0]["logs"] = "invented"
    elif change == "bool-id":
        fixture["with_"]["run_id"] = True
    elif change == "missing-fixture":
        world["probes"]["gh.actions.run.jobs"] = []
    elif change == "unexpected-operation":
        world["probes"]["shell.command"] = [fixture]
    else:
        fixture["with_"]["attempt"] = 4
    with pytest.raises(ValueError):
        verify(example(), overrides=world)


def test_empty_complete_collection_is_valid_and_registered_attempt_is_not_latest_default():
    world = deepcopy(describe_help_snippet_worlds()["gh-actions-bridge"])
    world["probes"]["gh.actions.run"][0]["outputs"].update(run_id=901, run_attempt=7)
    fixture = world["probes"]["gh.actions.run.jobs"][0]
    fixture["with_"].update(run_id=901, attempt=7)
    fixture["outputs"].update(run_id=901, run_attempt=7, items=[], count=0)
    result = verify(example(), overrides=world)
    assert result.status == "ok"
    assert result.runtime_result.published == ({"run_id": 901, "run_attempt": 7, "items": [], "count": 0, "complete": True},)


def test_call_budget_is_enforced():
    from ordo.runtime import execute_workflow, load_workflow_text
    from dataclasses import replace

    world = describe_help_snippet_worlds()["gh-actions-direct"]
    calls = []
    provider = normalized_fixture_provider(world, references={"gh.actions.run", "gh.actions.run.jobs"}, calls=calls, call_budget=1)
    workflow = replace(load_workflow_text(example("direct")["yaml"]), inputs=world["inputs"])
    with pytest.raises(ValueError, match="call budget"):
        execute_workflow(workflow, connector_provider=provider)
    assert len(calls) == 1


def test_world_inputs_are_declared_and_scaffold_preserves_source():
    from ordo.runtime.help_snippet_scaffolds import INSERTION_CONTRACTS, build_workflow_fragment_scaffold

    for handle in GH_ACTIONS_TARGETS:
        assert handle in INSERTION_CONTRACTS["workflow_fragment"].supported_targets
        assert build_workflow_fragment_scaffold(target=handle, snippet=example()["yaml"]) == example()["yaml"]
    with pytest.raises(ValueError, match="declared workflow inputs"):
        verify(example(), overrides={"inputs": {"merge_allowed": True}})
