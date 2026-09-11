"""Exact displayed PR-list YAML, exercised with no subprocess or live provider."""

from copy import deepcopy

import pytest

from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.model.help_snippets import describe_help_snippets
from ordo.runtime.help_snippet_runner import verify_help_snippet
from ordo.runtime.help_snippet_scaffolds import build_workflow_fragment_scaffold


CASES = ("no_pr", "exactly_one_open", "ambiguous_multiple_open", "only_closed_history", "unknown_metadata")


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Snippet verification attempted live execution")

    for path in ("subprocess.run", "subprocess.Popen", "ordo.connectors.operations.evaluate_probe",
                 "ordo.connectors.operations.execute_operation", "ordo.runtime.providers.get_default_connector_provider"):
        monkeypatch.setattr(path, forbidden)


def example(case):
    return next(item for item in describe_help_snippets()["connector.gh.pr.list"]["canonical_examples"]
                if item["name"] == f"gh_pr_list_{case}")


def run(case="exactly_one_open", overrides=None, **kwargs):
    item = example(case)
    args = {"snippet": item["yaml"], "world": item["verification"]["world"],
            "insertion_mode": "workflow_fragment", "target": "connector.gh.pr.list", "overrides": overrides}
    return verify_help_snippet(**{**args, **kwargs})


def probes(case="exactly_one_open"):
    return deepcopy(describe_help_snippet_worlds()[example(case)["verification"]["world"]]["probes"])


@pytest.mark.parametrize("case,counts", tuple(zip(CASES, (
    (0, 0, 0, 0, 0), (1, 1, 0, 0, 0), (2, 2, 0, 0, 0), (2, 0, 2, 1, 0), None,
))))
def test_exact_published_workflow_classifies_all_worlds(case, counts):
    result = run(case)
    assert result.verification_path == "fixture_execution"
    assert result.workflow_text == example(case)["yaml"]
    assert build_workflow_fragment_scaffold(target="connector.gh.pr.list", snippet=result.workflow_text) == result.workflow_text
    assert result.status == example(case)["verification"]["expected_status"], result.runtime_result.to_contract()
    assert 0 < len(result.calls) <= 20
    expected_inputs = probes(case)["gh.pr.list"][0]["with_"]
    assert all(call["reference"] == "gh.pr.list" and call["inputs"] == expected_inputs for call in result.calls)
    if counts is None:
        assert not result.runtime_result.published
    else:
        assert result.runtime_result.published == (dict(zip(("count", "open", "closed", "merged", "merged_unknown"), counts)),
                                                  {"classification": case})


@pytest.mark.parametrize("field", ("head_repository", "head_repository_key", "head_owner", "head_ref", "base_repository", "base_ref"))
def test_unknown_identity_cannot_be_filtered_away_as_no_pr(field):
    fixture = probes()
    fixture["gh.pr.list"][0]["outputs"]["items"][1][field] = None
    result = run(overrides={"probes": fixture, "inputs": {"head_repository": "contributor/absent"}})
    assert result.status == "execution_error"
    assert any(d.code == "runtime.step.gate.failed" for d in result.runtime_result.diagnostics)
    assert not result.runtime_result.published


@pytest.mark.parametrize("caller_repository,classification,count", (
    ("CONTRIBUTOR/MOBILE-APP", "exactly_one_open", 1),
    ("contributor/mobile-app", "exactly_one_open", 1),
    ("Contributor/Other-Repository", "no_pr", 0),
))
def test_exact_repository_comparison_uses_probe_key(caller_repository, classification, count):
    fixture = probes()
    item = fixture["gh.pr.list"][0]["outputs"]["items"][0]
    item["head_repository"] = "Contributor/Mobile-App"
    item["head_repository_key"] = "contributor/mobile-app"
    result = run(overrides={"probes": fixture, "inputs": {"head_repository": caller_repository}})
    assert result.status == "ok", result.runtime_result.to_contract()
    assert result.runtime_result.published[0]["count"] == count
    assert result.runtime_result.published[-1] == {"classification": classification}
    assert result.effective_world["probes"]["gh.pr.list"][0]["outputs"]["items"][0]["head_repository"] == "Contributor/Mobile-App"
    assert all(call["inputs"]["head"] == "task/42" for call in result.calls)


@pytest.mark.parametrize("key_value", (None, "", "missing"))
def test_unknown_repository_key_blocks_before_false_absence(key_value):
    fixture = probes()
    item = fixture["gh.pr.list"][0]["outputs"]["items"][1]
    if key_value == "missing":
        del item["head_repository_key"]
    else:
        item["head_repository_key"] = key_value
    result = run(overrides={"probes": fixture, "inputs": {"head_repository": "Contributor/Absent"}})
    assert result.status != "ok"
    assert not result.runtime_result.published


def test_unknown_merge_fact_remains_unknown():
    fixture = probes()
    fixture["gh.pr.list"][0]["outputs"]["items"][0]["merged"] = None
    result = run(overrides={"probes": fixture})
    assert result.status == "ok", result.runtime_result.to_contract()
    assert result.runtime_result.published[0]["merged_unknown"] == 1
    assert result.runtime_result.published[0]["merged"] == 0


@pytest.mark.parametrize("field,value", (("complete", False), ("count", 99)))
def test_incomplete_or_inconsistent_observation_blocks(field, value):
    fixture = probes()
    fixture["gh.pr.list"][0]["outputs"][field] = value
    result = run(overrides={"probes": fixture})
    assert result.status == "execution_error"
    assert any(d.code == "runtime.step.gate.failed" for d in result.runtime_result.diagnostics)
    assert not result.runtime_result.published


@pytest.mark.parametrize("change", ({"head": "other"}, {"head_owner": "other"}, {"base": "other"}, {"repository": "acme/other"}))
def test_resolved_filter_mismatch_rejected(change):
    with pytest.raises(ValueError, match="Resolved fixture inputs differ"):
        run(overrides={"inputs": change})


@pytest.mark.parametrize("kwargs", ({"snippet": "version: 0\nworkflow: other\nblocks: []\n"},
                                  {"target": "connector.gh.pr"}, {"insertion_mode": "step_fragment"}))
def test_noncanonical_execution_rejected(kwargs):
    with pytest.raises(ValueError, match="exact published"):
        run(**kwargs)


def test_undeclared_input_rejected():
    with pytest.raises(ValueError, match="declared workflow inputs"):
        run(overrides={"inputs": {"create": True}})


def test_missing_public_contract_is_not_manufactured(monkeypatch):
    class MissingRegistry:
        def get_operation(self, reference):
            return None

    monkeypatch.setattr("ordo.connectors.registry.get_public_connector_registry", MissingRegistry)
    with pytest.raises(ValueError, match="published output contract"):
        run()


def test_probe_failure_does_not_publish_partial_success():
    fixture = probes()
    fixture["gh.pr.list"][0]["status"] = "failed"
    result = run(overrides={"probes": fixture})
    assert result.status != "ok"
    assert not result.runtime_result.published


def test_resolved_fixture_comparison_is_type_strict():
    fixture = probes()
    fixture["gh.pr.list"][0]["with_"]["head"] = True
    with pytest.raises(ValueError, match="Resolved fixture inputs differ"):
        run(overrides={"inputs": {"head": 1}, "probes": fixture})


@pytest.mark.parametrize("mode", ("check", "review", "plan", "explain", "next"))
def test_non_execution_modes_admit_canonical_workflow(mode, monkeypatch):
    from ordo import runtime
    from ordo.runtime.nexting import build_next_candidate

    def inspect(workflow, *, connector_provider):
        evaluate = getattr(runtime, f"{'explain' if mode == 'next' else mode}_workflow")
        result = evaluate(workflow, connector_provider=connector_provider)
        assert result.status.value == "ok", result.to_contract()
        if mode == "next":
            monkeypatch.setattr("ordo.runtime.resolution.get_default_connector_provider", lambda: connector_provider)
            candidate = build_next_candidate(
                workflow=workflow.workflow, description=None, workflow_category=None,
                when=None, working_directory=None, runtime_result=result,
                workflow_contract=workflow, runtime_workflow=workflow,
            )
            assert candidate.allowed
            assert not candidate.missing_inputs
        return result

    monkeypatch.setattr("ordo.runtime.executing.execute_workflow", inspect)
    run()


@pytest.mark.parametrize("scenario", ("budget", "forbidden-operation"))
def test_fixture_provider_has_no_fallback_and_enforces_budget(scenario, monkeypatch):
    from ordo.runtime.resolution import ResolvedOperation

    def inspect(workflow, *, connector_provider):
        reference = "gh.pr.list" if scenario == "budget" else "gh.pr.merge"
        resolved = ResolvedOperation(reference=reference, connector_namespace="gh",
                                     operation=connector_provider.registry.get_operation(reference), source="public", declared_with={},
                                     resolved_inputs=probes()["gh.pr.list"][0]["with_"])
        for _ in range(21):
            connector_provider.step_executor(resolved, workflow)

    monkeypatch.setattr("ordo.runtime.executing.execute_workflow", inspect)
    with pytest.raises(ValueError, match="20-call fixture budget" if scenario == "budget" else "Only gh.pr.list"):
        run()
