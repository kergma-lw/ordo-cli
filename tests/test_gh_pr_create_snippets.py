"""Execute displayed create-only YAML with strict fixtures and no live dispatch."""

from copy import deepcopy

import pytest

from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.model.help_snippets import describe_help_snippets
from ordo.runtime.help_snippet_runner import verify_help_snippet
from ordo.runtime.help_snippet_scaffolds import build_workflow_fragment_scaffold


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Snippet attempted live execution")

    for path in ("subprocess.run", "subprocess.Popen", "ordo.connectors.operations.evaluate_probe",
                 "ordo.connectors.operations.execute_operation", "ordo.runtime.providers.get_default_connector_provider"):
        monkeypatch.setattr(path, forbidden)


def world():
    return deepcopy(describe_help_snippet_worlds()["gh-pr-create-new-only"])


def run(overrides=None, **kwargs):
    item = describe_help_snippets()["connector.gh.pr.create"]["canonical_examples"][0]
    return verify_help_snippet(**{
        "snippet": item["yaml"], "world": "gh-pr-create-new-only", "insertion_mode": "workflow_fragment",
        "target": "connector.gh.pr.create", "overrides": overrides, **kwargs,
    })


def test_create_once_and_observe_actual_saved_number():
    fixture = world()
    fixture["actions"]["gh.pr.create"]["outputs"].update(pull_number=109, pull_ref="acme/mobile-app#109")
    fixture["probes"]["gh.pr"][0]["with_"]["pull_number"] = 109
    result = run(fixture)
    assert result.status == "ok", str(result.runtime_result.to_contract())
    assert result.verification_path == "fixture_execution"
    assert build_workflow_fragment_scaffold(target=result.target, snippet=result.workflow_text) == result.workflow_text
    assert [c["reference"] for c in result.calls if c["phase"] == "execute"] == ["gh.pr.list", "gh.pr.create", "gh.pr"]
    assert result.calls[-1]["inputs"]["pull_number"] == 109
    assert len(result.runtime_result.published) == 1
    assert result.runtime_result.published[0]["pull_number"] == 109


@pytest.mark.parametrize("inputs", ({"authorize_create": False}, {"draft": "true"}, {"head_owner": "other"}))
def test_authorization_and_consistency_block_before_calls(inputs):
    result = run({"inputs": inputs})
    assert result.status != "ok"
    assert not result.calls
    assert not result.runtime_result.published


def test_authorization_default_is_false():
    fixture = world()
    fixture["inputs"].pop("authorize_create")
    # Deep-merge overrides cannot remove a default world's input. Replace the
    # published world for this test so workflow loading supplies its own default.
    from unittest.mock import patch
    with patch("ordo.runtime.help_snippet_runner.describe_help_snippet_worlds", return_value={"gh-pr-create-new-only": fixture}):
        result = run()
    assert not result.calls
    assert result.status != "ok"


@pytest.mark.parametrize("case", ("exactly-one-open", "ambiguous-multiple-open", "only-closed-history", "unknown-metadata"))
def test_existing_or_unknown_identity_blocks_before_create(case):
    probes = describe_help_snippet_worlds()[f"gh-pr-list-{case}"]["probes"]
    result = run({"probes": probes})
    assert result.status != "ok"
    assert all(c["reference"] == "gh.pr.list" for c in result.calls)
    assert result.calls
    assert result.runtime_result.failed_step == (
        "require-complete-known-identity" if case == "unknown-metadata" else "require-no-existing-pr")
    assert not result.runtime_result.published


def test_casing_does_not_manufacture_absence():
    probes = describe_help_snippet_worlds()["gh-pr-list-exactly-one-open"]["probes"]
    probes["gh.pr.list"][0]["outputs"]["items"][0]["head_repository"] = "Contributor/Mobile-App"
    result = run({"inputs": {"head_repository": "CONTRIBUTOR/MOBILE-APP"}, "probes": probes})
    assert result.status != "ok"
    assert all(c["reference"] == "gh.pr.list" for c in result.calls)


@pytest.mark.parametrize("outcome", ("already_exists", "provider_error"))
def test_action_failure_stops_without_retry_or_false_publication(outcome):
    fixture = world()
    fixture["actions"]["gh.pr.create"].update(status="failed", outputs={"created": False, "reason": outcome})
    result = run(fixture)
    assert result.status != "ok"
    assert sum(c["reference"] == "gh.pr.create" for c in result.calls) == 1
    assert not any(c["reference"] == "gh.pr" for c in result.calls)
    assert not result.runtime_result.published


@pytest.mark.parametrize("output", ({"created": None}, {"created": False}, {"pull_number": None}, {"pull_number": 0}))
def test_unknown_creation_cannot_publish_success(output):
    fixture = world()
    fixture["actions"]["gh.pr.create"]["outputs"].update(output)
    result = run(fixture)
    assert result.status != "ok"
    assert not any(c["reference"] == "gh.pr" for c in result.calls)
    assert not result.runtime_result.published


def test_strict_resolved_action_inputs():
    with pytest.raises(ValueError, match="Resolved fixture inputs differ"):
        run({"inputs": {"title": "different"}})


@pytest.mark.parametrize("kwargs", ({"snippet": "version: 0"}, {"target": "connector.gh.pr"}, {"insertion_mode": "step_fragment"}))
def test_noncanonical_text_or_handle_rejected(kwargs):
    with pytest.raises(ValueError, match="exact published"):
        run(**kwargs)


@pytest.mark.parametrize("mode", ("check", "review", "plan", "explain", "next"))
def test_other_runtime_modes_admit_workflow(mode, monkeypatch):
    from ordo import runtime
    from ordo.runtime.nexting import build_next_candidate

    def inspect(workflow, *, connector_provider):
        evaluate = (runtime.assess_workflow_readiness if mode in ("explain", "next")
                    else getattr(runtime, f"{mode}_workflow"))
        result = evaluate(
            workflow, connector_provider=connector_provider)
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


@pytest.mark.parametrize("scenario", ("budget", "forbidden-operation", "duplicate-create"))
def test_provider_is_bounded_and_has_no_fallback(scenario, monkeypatch):
    from ordo.runtime.resolution import ResolvedOperation

    def inspect(workflow, *, connector_provider):
        reference = {"budget": "gh.pr.list", "forbidden-operation": "gh.pr.merge",
                     "duplicate-create": "gh.pr.create"}[scenario]
        fixture = world()
        inputs = (fixture["actions"][reference]["with_"] if scenario == "duplicate-create"
                  else fixture["probes"]["gh.pr.list"][0]["with_"])
        resolved = ResolvedOperation(reference=reference, connector_namespace="gh",
                                     operation=connector_provider.registry.get_operation(reference), source="public",
                                     declared_with={}, resolved_inputs=inputs)
        for _ in range(21):
            connector_provider.step_executor(resolved, workflow)

    monkeypatch.setattr("ordo.runtime.executing.execute_workflow", inspect)
    message = {"budget": "20-call fixture budget", "forbidden-operation": "No fixture execution",
               "duplicate-create": "one execution-time submission"}[scenario]
    with pytest.raises(ValueError, match=message):
        run()


def test_missing_contract_is_not_manufactured(monkeypatch):
    class MissingRegistry:
        def get_operation(self, reference):
            return None

    monkeypatch.setattr("ordo.connectors.registry.get_public_connector_registry", MissingRegistry)
    with pytest.raises(ValueError, match="published output contract"):
        run()


@pytest.mark.parametrize("field", ("head_repository", "head_repository_key", "head_owner", "head_ref", "base_repository", "base_ref"))
def test_unknown_candidate_identity_cannot_be_filtered_away(field):
    probes = describe_help_snippet_worlds()["gh-pr-list-exactly-one-open"]["probes"]
    probes["gh.pr.list"][0]["outputs"]["items"][1][field] = None
    result = run({"probes": probes})
    assert result.runtime_result.failed_step == "require-complete-known-identity"
    assert not any(c["reference"] == "gh.pr.create" for c in result.calls)


@pytest.mark.parametrize("output", ({"complete": False}, {"count": 8}))
def test_incomplete_list_blocks_create(output):
    fixture = world()
    fixture["probes"]["gh.pr.list"][0]["outputs"].update(output)
    result = run(fixture)
    assert result.runtime_result.failed_step == "require-complete-known-identity"
    assert not any(c["reference"] == "gh.pr.create" for c in result.calls)
