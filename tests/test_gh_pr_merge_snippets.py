"""Execute the exact displayed merge workflows, exclusively against strict fixtures.

These tests establish workflow admission, SHA/UUID handoff and honest publication;
connector HTTP behavior belongs to test_gh_pr_merge/test_gh_pr_observation.
"""

from copy import deepcopy

import pytest

from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.model.help_snippets import describe_help_snippets
from ordo.runtime import load_workflow_text
from ordo.runtime.help_snippet_runner import verify_help_snippet
from ordo.runtime.help_snippet_scaffolds import GH_PR_MERGE_TARGETS, build_workflow_fragment_scaffold


NAMES = ("gh_pr_async_merge_head", "gh_pr_async_merge_test_merge", "gh_pr_async_merge_head_context")


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Snippet verification attempted live execution")

    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("ordo.connectors.operations.evaluate_probe", forbidden)
    monkeypatch.setattr("ordo.connectors.operations.execute_operation", forbidden)
    monkeypatch.setattr("ordo.runtime.providers.get_default_connector_provider", forbidden)


def example(name, handle="connector.gh.pr.merge"):
    return next(item for item in describe_help_snippets()[handle]["canonical_examples"] if item["name"] == name)


def run_example(name, overrides=None, handle="connector.gh.pr.merge"):
    item = example(name, handle)
    verification = item["verification"]
    return verify_help_snippet(
        snippet=item["yaml"], world=verification["world"],
        insertion_mode=verification["insertion_mode"], target=verification["target"], overrides=overrides,
    )


def probes(name):
    return deepcopy(describe_help_snippet_worlds()[example(name)["verification"]["world"]]["probes"])


def actions(result):
    return [call for call in result.calls if call["reference"] == "gh.pr.merge"]


def assert_blocked(result):
    assert result.verification_path == "fixture_execution"
    assert result.status != "ok", result.runtime_result.to_contract()
    assert not actions(result)
    assert not result.runtime_result.published


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("handle", GH_PR_MERGE_TARGETS)
def test_displayed_workflow_executes_with_pinned_head_and_saved_uuid(name, handle):
    item = example(name, handle)
    result = run_example(name, handle=handle)
    assert result.status == "ok", result.runtime_result.to_contract()
    assert result.verification_path == "fixture_execution"
    assert result.workflow_text == item["yaml"]
    assert build_workflow_fragment_scaffold(target=handle, snippet=item["yaml"]) == item["yaml"]
    assert len(actions(result)) == 1
    assert actions(result)[0]["inputs"]["expected_head_sha"] == "a" * 40
    checks = [call for call in result.calls if call["reference"] == "gh.pr.checks"]
    assert checks and all(call["inputs"]["expected_head_sha"] == "a" * 40 for call in checks)
    request_calls = [call for call in result.calls if call["reference"] == "gh.pr.merge.request"]
    assert request_calls
    assert all(call["inputs"]["request_id"] == "12345678-1234-1234-1234-123456789abc" for call in request_calls)
    assert result.runtime_result.outputs["executed_steps"].count("observe-saved-request-once") == 1
    assert result.runtime_result.published[-1] == {"merged": True, "merge_commit_sha": "d" * 40}
    assert result.calls[-1]["reference"] == "gh.pr"


@pytest.mark.parametrize("name", NAMES)
def test_workflow_authorization_defaults_false(name, monkeypatch):
    item = example(name)
    assert load_workflow_text(item["yaml"]).inputs["authorize_merge"] is False
    worlds = describe_help_snippet_worlds()
    del worlds[item["verification"]["world"]]["inputs"]["authorize_merge"]
    monkeypatch.setattr("ordo.runtime.help_snippet_runner.describe_help_snippet_worlds", lambda: worlds)
    result = run_example(name)
    assert_blocked(result)
    assert not result.calls


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("state", ("stacked", "unknown", None))
def test_non_standalone_pr_does_not_submit(name, state):
    fixture = probes(name)
    fixture["gh.pr"][0]["outputs"]["stack_state"] = state
    assert_blocked(run_example(name, {"probes": fixture}))


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("authorization", (False, "true", None, 1))
def test_authorization_requires_boolean_true(name, authorization):
    assert_blocked(run_example(name, {"inputs": {"authorize_merge": authorization}}))


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("field", ("head_sha", "expected_head_sha", "commit_sha"))
def test_mismatched_sha_cannot_submit(name, field):
    fixture = probes(name)
    fixture["gh.pr.checks"][0]["outputs"][field] = "e" * 40
    assert_blocked(run_example(name, {"probes": fixture}))


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("scenario", ("missing", "pending", "failed", "skipped", "wrong-app", "wrong-name", "wrong-sha", "unknown", "incomplete", "duplicate"))
def test_ci_admission_is_explicit_and_fail_closed(name, scenario):
    fixture = probes(name)
    ci = fixture["gh.pr.checks"][0]["outputs"]
    check = ci["checks"][0]
    # Leave overall_state successful for per-check cases to prove the explicit
    # identity/status/conclusion requirement independently of aggregate status.
    if scenario == "missing":
        ci["checks"] = []
    elif scenario == "pending":
        check.update(status="in_progress", conclusion=None)
    elif scenario in {"failed", "skipped"}:
        check["conclusion"] = "failure" if scenario == "failed" else "skipped"
    elif scenario == "wrong-app":
        check["app_id"] = 999
    elif scenario == "wrong-name":
        check["name"] = "unrequired-check"
    elif scenario == "wrong-sha":
        check["sha"] = "e" * 40
    elif scenario == "unknown":
        ci["overall_state"] = "unknown"
    elif scenario == "incomplete":
        ci["complete"] = False
    elif scenario == "duplicate":
        ci["checks"].append(deepcopy(check))
    assert_blocked(run_example(name, {"probes": fixture}))


@pytest.mark.parametrize("field,value", (
    ("base_sha", "e" * 40), ("test_merge_base_sha", "e" * 40),
    ("test_merge_head_sha", "e" * 40), ("test_merge_sha", "e" * 40),
    ("test_merge_state", "identity_mismatch"),
))
def test_test_merge_candidate_must_remain_tied_to_saved_head_and_base(field, value):
    name = NAMES[1]
    fixture = probes(name)
    fixture["gh.pr.checks"][0]["outputs"][field] = value
    assert_blocked(run_example(name, {"probes": fixture}))


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("field", ("statuses_complete", "check_runs_complete"))
def test_incomplete_pagination_is_not_accepted(name, field):
    fixture = probes(name)
    fixture["gh.pr.checks"][0]["outputs"][field] = False
    assert_blocked(run_example(name, {"probes": fixture}))


@pytest.mark.parametrize("field", ("test_merge_head_sha", "test_merge_base_sha"))
def test_initial_test_candidate_requires_verified_parents(field):
    fixture = probes(NAMES[1])
    fixture["gh.pr"][0]["outputs"][field] = "e" * 40
    assert_blocked(run_example(NAMES[1], {"probes": fixture}))


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("state", ("pending", "failed", "enqueued", "merged"))
def test_request_state_is_published_but_not_used_as_final_merge_proof(name, state):
    fixture = probes(name)
    fixture["gh.pr.merge.request"][0]["outputs"].update(
        state=state, merged=state == "merged", message=f"Request {state}",
        merge_sha="d" * 40 if state == "merged" else None,
    )
    fixture["gh.pr"][1]["outputs"].update(merged=False, merge_commit_sha=None, state="open")
    result = run_example(name, {"probes": fixture})
    assert result.status == "ok", result.runtime_result.to_contract()
    assert result.runtime_result.published[1]["request_state"] == state
    assert result.runtime_result.published[-1] == {"merged": False, "merge_commit_sha": None}


@pytest.mark.parametrize("name", NAMES)
def test_unknown_final_merge_fact_remains_unknown(name):
    fixture = probes(name)
    fixture["gh.pr"][1]["outputs"].update(merged=None, merge_commit_sha=None)
    result = run_example(name, {"probes": fixture})
    assert result.status == "ok", result.runtime_result.to_contract()
    assert result.runtime_result.published[-1] == {"merged": None, "merge_commit_sha": None}


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("state", ("merged", "enqueued"))
def test_already_merged_or_enqueued_without_uuid_skips_request_safely(name, state):
    fixture = probes(name)
    fixture["gh.pr"][1]["outputs"].update(merged=state == "merged", merge_commit_sha="d" * 40 if state == "merged" else None)
    result = run_example(name, {"probes": fixture, "actions": {"gh.pr.merge": {"outputs": {
        "request_id": None, "state": state, "merged": state == "merged", "submission": f"already_{state}",
        "http_status": 200, "merge_sha": "d" * 40 if state == "merged" else None,
    }}}})
    assert result.status == "ok", result.runtime_result.to_contract()
    assert not [call for call in result.calls if call["reference"] == "gh.pr.merge.request"]
    assert len(result.runtime_result.published) == 2
    assert result.runtime_result.published[-1]["merged"] is (state == "merged")


@pytest.mark.parametrize("name", NAMES)
def test_uuid_handoff_uses_saved_action_output(name):
    request_id = "87654321-4321-4321-4321-cba987654321"
    fixture = probes(name)
    fixture["gh.pr.merge.request"][0]["with_"]["request_id"] = request_id
    fixture["gh.pr.merge.request"][0]["outputs"]["request_id"] = request_id
    result = run_example(name, {"probes": fixture, "actions": {"gh.pr.merge": {"outputs": {"request_id": request_id}}}})
    assert result.status == "ok", result.runtime_result.to_contract()
    assert result.runtime_result.published[0]["request_id"] == request_id
    assert result.runtime_result.published[1]["request_id"] == request_id


@pytest.mark.parametrize("name", NAMES)
def test_action_fixture_matching_is_strict(name):
    with pytest.raises(ValueError, match="Resolved fixture inputs differ for gh.pr.merge"):
        run_example(name, {"actions": {"gh.pr.merge": {"with_": {"expected_head_sha": "e" * 40}}}})


def test_fixture_execution_rejects_noncanonical_yaml_instead_of_falling_back():
    item = example(NAMES[0])
    with pytest.raises(ValueError, match="exact published"):
        verify_help_snippet(snippet=item["yaml"] + "\n# different document\n", world=item["verification"]["world"],
                            insertion_mode="workflow_fragment", target="connector.gh.pr.merge")


def test_existing_world_validation_is_not_reported_as_execution():
    result = verify_help_snippet(snippet="inputs.close_comment | is_string", world="default", insertion_mode="step_field", target="workflow.step.if")
    assert result.status == "ok"
    assert result.verification_path == "validation_only"
    assert result.runtime_result is None
    assert not result.calls


def test_context_example_omits_only_merge_repository_and_keeps_identity_pinned():
    workflow = load_workflow_text(example(NAMES[2])["yaml"])
    assert workflow.connector_contexts == {}  # Context comes from composition, not workflow YAML.
    result = run_example(NAMES[2])
    assert result.effective_world["connector_contexts"] == {"gh": {"repository": "acme/mobile-app"}}
    assert result.status == "ok", result.runtime_result.to_contract()
    for call in result.calls:
        if call["reference"] in {"gh.pr.merge", "gh.pr.merge.request"}:
            assert "repository" not in call["inputs"]
        else:
            assert call["inputs"]["repository"] == "acme/mobile-app"


def test_context_example_blocks_cross_repository_observation():
    result = run_example(NAMES[2], {"inputs": {"repository": "other/repo"}})
    assert_blocked(result)
    assert not result.calls


@pytest.mark.parametrize("context", (None, {"gh": {"repository": None}}, {"gh": {"repository": "inputs.repository"}}))
def test_context_world_requires_literal_runtime_context(context):
    with pytest.raises(ValueError, match="published literal gh repository"):
        run_example(NAMES[2], {"connector_contexts": context})


@pytest.mark.parametrize("reference", ("gh.pr.merge", "gh.pr.merge.request"))
def test_context_fixture_cannot_claim_another_output_repository(reference):
    if reference == "gh.pr.merge":
        overrides = {"actions": {reference: {"outputs": {"repository": "other/repo"}}}}
    else:
        fixture = probes(NAMES[2])
        fixture[reference][0]["outputs"]["repository"] = "other/repo"
        overrides = {"probes": fixture}
    with pytest.raises(ValueError, match="Fixture output repository differs from gh context"):
        run_example(NAMES[2], overrides)


@pytest.mark.parametrize("mode", ("check", "review", "plan", "explain", "next"))
def test_context_workflow_is_admitted_by_non_execution_modes(mode, monkeypatch):
    from ordo import runtime
    from ordo.runtime.nexting import build_next_candidate

    def inspect(workflow, *, connector_provider):
        assert workflow.connector_contexts == {"gh": {"repository": "acme/mobile-app"}}
        evaluate = (runtime.assess_workflow_readiness if mode in ("explain", "next")
                    else getattr(runtime, f"{mode}_workflow"))
        result = evaluate(workflow, connector_provider=connector_provider)
        assert result.status.value == "ok", result.to_contract()
        if mode == "next":
            # Next's static topology analysis uses the composition registry.
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
    result = run_example(NAMES[2])
    assert not actions(result)
