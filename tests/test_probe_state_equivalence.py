from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import check_workflow, execute_workflow, assess_workflow_readiness, plan_workflow, review_workflow
from ordo.runtime.checking import _canonicalize_probe_descriptor, _observation_covers
from ordo.runtime.nexting import build_next_candidate
from tests.support import STANDARD_CONNECTOR_PROVIDER


@pytest.fixture
def workflow(tmp_path):
    return Workflow(
        version=0,
        workflow="state-probe-equivalence",
        inputs={"repository": "acme/repo", "project_id": "PVT_demo"},
        state_needs={"shared_state": {}},
        state_bindings={"shared_state": "store"},
        states={"store": str(tmp_path / "state.json")},
        let_bindings={
            "saved": 'state.shared_state["key"]',
            "probe": "gh.project.issue(repository=inputs.repository, project_id=inputs.project_id, issue_number=saved)",
        },
        blocks=(
            GuardBlock(guards=(
                Guard(expr="probe.exists"),
                Guard(expr='gh.project.field(project_id=inputs.project_id, field="Status").exists'),
                Guard(expr='gh.project.field.option(project_id=inputs.project_id, field="Status", option="Done").exists'),
            )),
            StepBlock(steps=(Step(
                name="set-status",
                operation=OperationRef("gh.project.issue.field_single_select.set", with_={
                    "repository": "inputs.repository",
                    "project_id": "inputs.project_id",
                    "issue_number": "saved",
                    "field": "Status",
                    "option": "Done",
                }),
            ),)),
        ),
    )


@pytest.mark.parametrize("value", ["saved", "${saved}", 'state.shared_state["key"]', {'expression': 'state.shared_state["key"]'}])
def test_state_alias_has_canonical_expression_wrapper(workflow, value):
    assert _canonicalize_probe_descriptor(value, workflow=workflow) == {
        "expression": 'state.shared_state["key"]',
    }


@pytest.mark.parametrize("different", [
    {"with": {"issue_number": 'state.shared_state["other"]', "project_id": "inputs.project_id"}},
    {"with": {"issue_number": 'state.shared_state["key"].number', "project_id": "inputs.project_id"}},
    {"with": {"issue_number": 'state.other_state["key"]', "project_id": "inputs.project_id"}},
    {"with": {"issue_number": "saved", "project_id": "inputs.other_project_id"}},
    {"fields": ["id"]},
    {"probe": "gh.issue"},
])
def test_different_descriptors_remain_unmatched(workflow, different):
    required = {"probe": "gh.project.issue", "with": {"issue_number": "saved", "project_id": "inputs.project_id"}, "fields": ["exists"]}
    available = {**required, **different}
    assert not _observation_covers(available, required, available_workflow=workflow, required_workflow=workflow)


@pytest.mark.parametrize("literal", ['"key"', "7", "true", "null"])
def test_ordinary_literals_do_not_gain_expression_equivalence(workflow, literal):
    assert _canonicalize_probe_descriptor(literal, workflow=workflow) == literal
    assert _canonicalize_probe_descriptor({"expression": literal}, workflow=workflow) == {"expression": literal}
    assert not _observation_covers(
        {"probe": "gh.issue", "with": {"issue_number": literal}},
        {"probe": "gh.issue", "with": {"issue_number": {"expression": literal}}},
        available_workflow=workflow, required_workflow=workflow,
    )


@pytest.mark.parametrize("mode", [check_workflow, review_workflow, plan_workflow, assess_workflow_readiness])
@pytest.mark.parametrize("state_present", [False, True])
@pytest.mark.parametrize("direct_probe_argument", [False, True])
def test_analysis_distinguishes_intent_from_observation(workflow, tmp_path, mode, state_present, direct_probe_argument):
    if direct_probe_argument:
        workflow = replace(workflow, let_bindings={
            **workflow.let_bindings,
            "probe": workflow.let_bindings["probe"].replace("issue_number=saved", 'issue_number=state.shared_state["key"]'),
        })
    if state_present:
        (tmp_path / "state.json").write_text('{"key": 7}')
    probe = Mock(return_value=OperationResult(status="ok", outputs={"exists": True}))
    result = mode(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    expected_status = RuntimeStatus.OK if state_present or mode is review_workflow else RuntimeStatus.GUARD_FAILED
    assert result.status is expected_status, result.diagnostics
    snapshot = result.outputs["check_snapshot"] if mode is review_workflow else result.outputs
    assert snapshot["allowed_state"] == ("allowed" if state_present else "blocked")
    if mode is not review_workflow:
        support = snapshot["preflight_step_items"][0]["preflight_support"]
        assert support["missing_probes"] == []
        if state_present and direct_probe_argument:
            assert support["strength"] == "strong"
            assert len(support["matched_probes"]) == 3
            assert support["unmaterialized_probes"] == []
        else:
            # Known separate gap: observed aliases currently lack expansion context.
            assert support["strength"] == "partial"
            assert any(item["probe"] == "gh.project.issue" for item in support["unmaterialized_probes"])
            assert not any(item["probe"] == "gh.project.issue" for item in support["matched_probes"])
    if state_present:
        assert probe.call_count == 3
    else:
        assert not any(call.args[0].reference == "gh.project.issue" for call in probe.call_args_list)
    if mode is review_workflow:
        codes = {item["code"] for item in result.outputs["findings"]}
        assert "review.workflow.missing_recommended_probe_coverage" not in codes
        assert ("review.workflow.recommended_probe_result_not_available" in codes) is (not (state_present and direct_probe_argument))
    if mode is assess_workflow_readiness:
        with patch("ordo.runtime.resolution.get_default_connector_provider", return_value=STANDARD_CONNECTOR_PROVIDER):
            candidate = build_next_candidate(
                workflow=workflow.workflow, description=None, workflow_category=None,
                when=None, working_directory=None, runtime_result=result, runtime_workflow=workflow,
            )
        assert candidate.allowed is state_present
    if state_present:
        assert (tmp_path / "state.json").read_text() == '{"key": 7}'
    else:
        assert not (tmp_path / "state.json").exists()


@pytest.mark.parametrize("state_present", [False, True])
def test_run_does_not_promote_authored_intent_to_execution(workflow, tmp_path, state_present):
    if state_present:
        (tmp_path / "state.json").write_text('{"key": 7}')
    probe = Mock(return_value=OperationResult(status="ok", outputs={"exists": True}))
    action = Mock(return_value=OperationResult(status="ok"))
    result = execute_workflow(workflow, guard_probe=probe, step_executor=action, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    if state_present:
        assert result.status is RuntimeStatus.OK, result.diagnostics
        action.assert_called_once()
        assert action.call_args.args[0].resolved_inputs["issue_number"] == "saved"
        assert (tmp_path / "state.json").read_text() == '{"key": 7}'
    else:
        action.assert_not_called()
        assert result.status is not RuntimeStatus.OK
        assert not (tmp_path / "state.json").exists()
