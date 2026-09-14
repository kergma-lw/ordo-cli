from dataclasses import replace
from unittest.mock import patch

import pytest

from ordo.model.runtime import RuntimeStatus
from ordo.model.profile import Profile
from ordo.cli import _summarize_check_payload
from ordo.runtime import check_workflow, execute_workflow, assess_workflow_readiness, review_workflow, load_workflow_file, load_workflow_text, plan_workflow
from ordo.runtime.nexting import build_next_candidate
from tests.support import STANDARD_CONNECTOR_PROVIDER
from tests.test_state_role_write_order import workflow_text


@pytest.fixture
def make_workflow(tmp_path):
    def make(steps, tail=""):
        return replace(
            load_workflow_text(workflow_text(steps, bindings="inputs:\n  missing: {required: false}\n") + tail),
            states={"store": str(tmp_path / "state.json")},
            state_bindings={"memory": "store"},
        )
    return make


@pytest.mark.parametrize("mutation", ['state_set:\n    state.memory["key"]: ${7}', 'state_delete: state.memory["key"]'])
@pytest.mark.parametrize("tree", [False, True])
def test_deferred_state_runs_once_in_order(make_workflow, tmp_path, mutation, tree):
    path = tmp_path / "state.json"
    path.write_text('{"key": 1}')
    workflow = make_workflow('- name: mutate\n  ' + mutation + '\n- name: value\n  value: ${true}\n  register: ready', '  - guards:\n      - "true"\n')
    kwargs = {"connector_provider": STANDARD_CONNECTOR_PROVIDER}
    plan = plan_workflow(workflow, **kwargs)
    assert plan.status is RuntimeStatus.OK, plan.diagnostics
    assert plan.outputs["allowed_state"] == "allowed"
    node = plan.outputs["execution_tree"]["blocks"][0]["children"][0]
    assert node["preflight"]["status"] == "deferred"
    assert node["reuse_policy"] == "not_reusable"
    assert node["planned_probe_result"] is None
    assert "outputs" not in node["preflight"]
    assert path.read_text() == '{"key": 1}'
    result = execute_workflow(workflow, execution_tree=plan.outputs["execution_tree"] if tree else None, **kwargs)
    assert result.status is RuntimeStatus.OK, result.diagnostics
    assert result.outputs["executed_steps"].count("mutate") == 1
    if tree:
        assert node["runtime_status"] == "done"
        assert node["divergence_status"] == "not_applicable"
    assert path.read_text() == ('{\n  "key": 7\n}\n' if mutation.startswith("state_set") else '{}\n')


@pytest.mark.parametrize("control,expected", [("", "blocked"), ('  if: "false"\n', "blocked"), ('  gate: "false"\n', "blocked"), ("  gate: inputs.missing\n", "unknown")])
def test_conditions_gates_and_later_false_guard(make_workflow, tmp_path, control, expected):
    workflow = make_workflow('- name: mutate\n' + control + '  state_delete: state.memory["key"]', '  - guards:\n      - "false"\n')
    result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.outputs["allowed_state"] == expected, result.diagnostics
    assert not (tmp_path / "state.json").exists()
    if "if:" in control:
        assert result.outputs["preflight_step_items"][0]["status"] == "skipped"


@pytest.mark.parametrize("separate", [False, True])
def test_loop_after_deferral_stays_barrier(make_workflow, separate):
    steps = '- name: mutate\n  state_delete: state.memory["key"]'
    loop = '- name: loop\n  for_each: ${[1]}\n  steps:\n    - name: value\n      value: ${true}'
    tail = '  - guards:\n      - "true"\n'
    if separate:
        tail = '  - steps:\n' + '\n'.join('      ' + line for line in loop.splitlines()) + '\n' + tail
    else:
        steps += '\n' + loop
    result = check_workflow(make_workflow(steps, tail), connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.outputs["allowed_state"] == "unknown"
    assert "state_deferral_invocation_barrier" in result.outputs["incomplete_reasons"]
    assert result.outputs["checked_guards"] == []


def test_nested_check_does_not_defer(make_workflow):
    workflow = make_workflow('- name: mutate\n  state_delete: state.memory["key"]', '  - guards:\n      - "true"\n')
    result = check_workflow(workflow, _nested_analysis=True, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.outputs["allowed_state"] == "unknown"
    assert result.outputs["checked_guards"] == []
    assert result.outputs["preflight_step_items"][0]["status"] == "halted"


@pytest.mark.parametrize("nested", [False, True])
def test_named_run_preserves_barrier_and_nested_context(tmp_path, nested):
    write = '- name: mutate\n  state_delete: state.memory["key"]'
    child = tmp_path / "child.yml"
    child.write_text(workflow_text(write if nested else '- name: value\n  value: ${true}') + '  - guards:\n      - "true"\n')
    parent = tmp_path / "parent.yml"
    parent.write_text(workflow_text(('' if nested else write + '\n') + '- name: child\n  run: child.yml') + '  - guards:\n      - "false"\n')
    workflow = replace(load_workflow_file(parent), states={"store": str(tmp_path / "state.json")}, state_bindings={"memory": "store"})
    result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.status is RuntimeStatus.OK, result.diagnostics
    assert result.outputs["allowed_state"] == "unknown"
    assert not result.outputs["checked_guards"]
    assert all(item["status"] != "deferred" for item in result.outputs["preflight_step_items"] if nested)
    assert not (tmp_path / "state.json").exists()


def test_unknown_after_deferral_is_not_missing_guard_fact(make_workflow):
    workflow = make_workflow('- name: mutate\n  state_delete: state.memory["key"]\n- name: unknown\n  value: ${inputs.missing}', '  - guards:\n      - "true"\n')
    result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.outputs["allowed_state"] == "unknown"
    summary = _summarize_check_payload({"mode": "check", "status": result.status.value, "outputs": result.outputs})
    assert summary["allowed"] is False
    assert summary["allowed_state"] == "unknown"
    assert summary["analysis_complete"] is False
    assert summary["incomplete_reasons"]
    assert summary["unevaluated_relevant_guards"] == ["true"]
    assert summary["missing_facts"] == []


@pytest.mark.parametrize("tree", [False, True])
def test_multiple_deferred_writes_execute_in_authored_order(make_workflow, tmp_path, tree):
    from ordo.runtime import executing

    workflow = make_workflow('- name: first\n  state_set:\n    state.memory["key"]: ${1}\n- name: second\n  state_set:\n    state.memory["key"]: ${2}', '  - guards:\n      - "true"\n')
    kwargs = {"connector_provider": STANDARD_CONNECTOR_PROVIDER}
    plan = plan_workflow(workflow, **kwargs)
    assert plan.outputs["allowed_state"] == "allowed"
    assert not (tmp_path / "state.json").exists()
    with patch.object(executing, "_execute_state_set", wraps=executing._execute_state_set) as writes:
        result = execute_workflow(workflow, execution_tree=plan.outputs["execution_tree"] if tree else None, **kwargs)
    assert result.status is RuntimeStatus.OK
    assert [call.args[0] for call in writes.call_args_list] == ["first", "second"]
    assert (tmp_path / "state.json").read_text() == '{\n  "key": 2\n}\n'


@pytest.mark.parametrize("separate", [False, True])
def test_profile_switch_cannot_resume_after_deferred_loop(make_workflow, separate):
    steps = '- name: mutate\n  state_delete: state.memory["key"]\n- name: loop\n  for_each: ${[1]}\n  steps:\n    - name: value\n      value: ${true}'
    switch = '- name: switch\n  profile_switch: other'
    tail = '  - guards:\n      - "true"\n'
    if separate:
        tail = '  - steps:\n' + '\n'.join('      ' + line for line in switch.splitlines()) + '\n' + tail
    else:
        steps += '\n' + switch
    result = check_workflow(make_workflow(steps, tail), available_profiles={"other": Profile(name="other")}, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.outputs["allowed_state"] == "unknown"
    assert not result.outputs["checked_guards"]
    assert result.outputs["active_profile"] is None


@pytest.mark.parametrize("mode", [check_workflow, plan_workflow, review_workflow, assess_workflow_readiness])
def test_read_write_then_unrelated_guard_is_read_only_in_analysis(make_workflow, tmp_path, mode):
    path = tmp_path / "state.json"
    path.write_text('{"key": 3}')
    workflow = make_workflow('- name: read\n  value: ${state.memory["key"]}\n  register: saved\n- name: mutate\n  state_set:\n    state.memory["key"]: ${step.saved.outputs.value}', '  - guards:\n      - "true"\n')
    result = mode(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.status is RuntimeStatus.OK, result.diagnostics
    verdict = result.outputs["check_snapshot"] if mode is review_workflow else result.outputs
    assert verdict["allowed_state"] == "allowed"
    assert verdict["analysis_complete"] is True
    assert result.analysis_tree.checked_guards == ("true",)
    assert path.read_text() == '{"key": 3}'
    if mode is assess_workflow_readiness:
        with patch("ordo.runtime.resolution.get_default_connector_provider", return_value=STANDARD_CONNECTOR_PROVIDER):
            candidate = build_next_candidate(workflow="ordering", description=None, workflow_category=None, when=None, working_directory=None, runtime_result=result, runtime_workflow=workflow)
        assert candidate.allowed
