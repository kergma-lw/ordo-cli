from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from ordo.model.profile import Profile
from ordo.model.runtime import RuntimeStatus
from ordo.runtime import execute_workflow, assess_workflow_readiness, load_workflow_file, load_workflow_text, validate_workflow_semantics, validate_workflow_text
from ordo.runtime.nexting import build_next_candidate
from tests.support import STANDARD_CONNECTOR_PROVIDER
from tests.test_state_role_write_order import workflow_text
from tests.test_state_storage_write_order import CODE, MODES


UNKNOWN = "validation.workflow.state_storage.identity_unresolved"


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "state.json").write_text('{"key": {"value": 7}}')
    return {
        "profile": Profile(name="a"),
        "available_profiles": {name: Profile(name=name) for name in ("a", "b")},
        "profile_working_directories": {name: tmp_path / name for name in ("a", "b")},
        "connector_provider": STANDARD_CONNECTOR_PROVIDER,
    }


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("shape", ("same-role-distinct", "same-role-alias", "same-name-distinct", "different-names-distinct", "same-relative-alias", "different-relative-alias", "hardlink"))
def test_storage_identity_follows_static_profile_switch(tmp_path, context, mode, shape):
    reader = "memory" if shape.startswith("same-role") else "other"
    states = {"store": "state.json", "alias": "state.json"}
    bindings = {"memory": "store", "other": "store" if shape == "same-name-distinct" else "alias"}
    invalid = shape in {"same-role-alias", "same-relative-alias", "different-relative-alias", "hardlink"}
    if shape in {"same-role-alias", "same-relative-alias"}:
        states = {"store": "../state.json", "alias": "../state.json"}
        (tmp_path / "state.json").write_text('{"key": {"value": 7}}')
    elif shape == "different-relative-alias":
        states["alias"] = "../a/state.json"
    elif shape == "hardlink":
        (tmp_path / "b" / "state.json").unlink()
        (tmp_path / "b" / "state.json").hardlink_to(tmp_path / "a" / "state.json")
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: "b"\n'
        '- name: read\n  publish:\n    value: state.' + reader + '["key"].value',
        guards="  - guards:\n      - git.worktree.clean\n" if invalid else "",
    )
    if shape == "same-role-distinct":
        assert not validate_workflow_text(text).ok
    workflow = replace(load_workflow_text(text), states=states, state_bindings=bindings)
    if invalid:
        probe = Mock(side_effect=AssertionError("unexpected observation"))
        executor = Mock(side_effect=AssertionError("unexpected effect"))
        kwargs = {"step_executor": executor} if mode is execute_workflow else {}
        with patch("subprocess.run", side_effect=AssertionError("unexpected external call")), patch(
            "ordo.runtime.local_expression_engine.core.read_state_document", side_effect=AssertionError("unexpected state read")
        ):
            result = mode(workflow, **context, guard_probe=probe, **kwargs)
        assert result.status is RuntimeStatus.VALIDATION_ERROR
        assert [d.code for d in result.diagnostics] == [CODE]
        assert not result.operation_results
        probe.assert_not_called()
        executor.assert_not_called()
        assert (tmp_path / "a" / "state.json").read_text() == '{"key": {"value": 7}}'
    else:
        result = mode(workflow, **context)
        assert result.status is RuntimeStatus.OK, result.diagnostics
        if mode is execute_workflow:
            assert (tmp_path / "a" / "state.json").read_text() == "{}\n"
            assert (tmp_path / "b" / "state.json").read_text() == '{"key": {"value": 7}}'


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("switch", ('${inputs.selected}', '${format("{}", inputs.selected)}', '${chosen}'))
def test_switch_resolves_inputs_and_let_without_probes(tmp_path, context, mode, switch):
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: ' + switch + '\n'
        '- name: read\n  publish:\n    value: state.other["key"]',
        bindings='inputs:\n  selected: {default: b}\nlet:\n  chosen: inputs.selected\n',
    )
    workflow = replace(load_workflow_text(text), states={"store": "state.json", "alias": "../a/state.json"}, state_bindings={"memory": "store", "other": "alias"})
    with patch("subprocess.run", side_effect=AssertionError("unexpected external call")):
        result = mode(workflow, **context)
    assert [d.code for d in result.diagnostics] == [CODE]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("switch", ('${state.other["profile"]}', '${gh.issue(repository="owner/repo", issue_number=1).title}'))
def test_unknown_switch_is_relevant_validation_error_before_observations(tmp_path, context, mode, switch):
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: ' + switch + '\n'
        '- name: read\n  publish:\n    value: state.memory["key"]',
        guards="  - guards:\n      - git.worktree.clean\n",
    )
    workflow = replace(load_workflow_text(text), states={"store": "state.json", "selector": str(tmp_path / "selector.json")}, state_bindings={"memory": "store", "other": "selector"})
    probe = Mock(side_effect=AssertionError("unexpected observation"))
    with patch("subprocess.run", side_effect=AssertionError("unexpected external call")), patch(
        "ordo.runtime.local_expression_engine.core.read_state_document", side_effect=AssertionError("unexpected state read")
    ):
        result = mode(workflow, **context, guard_probe=probe)
    assert result.status is RuntimeStatus.VALIDATION_ERROR
    assert [d.code for d in result.diagnostics] == [UNKNOWN]
    assert "not a proven ordering violation" in result.diagnostics[0].message
    assert result.diagnostics[0].details["context_path"] == ["blocks", "1", "steps", "1"]
    assert not result.operation_results
    probe.assert_not_called()
    if mode is assess_workflow_readiness:
        with patch("ordo.runtime.resolution.get_default_connector_provider", return_value=STANDARD_CONNECTOR_PROVIDER), patch(
            "ordo.runtime.checking.check_workflow", side_effect=AssertionError("next must not recheck")
        ):
            candidate = build_next_candidate(workflow="ordering", description=None, workflow_category=None, when=None, working_directory=None, runtime_result=result, runtime_workflow=workflow)
        assert not candidate.allowed
        assert UNKNOWN in [d.code for d in candidate.diagnostics]


@pytest.mark.parametrize("shape", ("read-only", "absolute-distinct", "read-before-write"))
def test_unknown_switch_is_not_a_blanket_rejection(tmp_path, context, shape):
    switch = '- name: switch\n  profile_switch: ${state.other["profile"]}\n'
    read = '- name: read\n  publish:\n    value: state.other["key"]\n'
    write = '- name: mutate\n  state_delete: state.memory["key"]\n'
    steps = switch + read if shape == "read-only" else switch + read + write if shape == "read-before-write" else write + switch + read
    workflow = replace(
        load_workflow_text(workflow_text(steps)), state_bindings={"memory": "store", "other": "alias"},
        states={"store": str(tmp_path / "one.json"), "alias": str(tmp_path / "two.json")} if shape == "absolute-distinct" else {"store": "one.json", "alias": "two.json"},
    )
    with patch("ordo.runtime.local_expression_engine.core.read_state_document", side_effect=AssertionError("unexpected state read")):
        report = validate_workflow_semantics(workflow, state_base_dir=tmp_path / "a", available_profiles=context["available_profiles"], profile_working_directories=context["profile_working_directories"])
    assert report.ok, report.diagnostics


@pytest.mark.parametrize("surface", ("if", "gate"))
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("overlap", (True, False))
def test_condition_cwd_mismatch_is_not_misclassified(tmp_path, context, surface, mode, overlap):
    writer = tmp_path / ("state.json" if overlap else "unrelated.json")
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: "b"\n'
        '- name: read\n  ' + surface + ': state.other["key"].value == 7\n  value: ${1}',
    )
    workflow = replace(load_workflow_text(text), state_bindings={"memory": "store", "other": "alias"}, states={"store": str(writer), "alias": "state.json"})
    if overlap:
        result = mode(workflow, **context)
        assert result.status is RuntimeStatus.VALIDATION_ERROR
        assert [d.code for d in result.diagnostics] == [UNKNOWN if surface == "if" else CODE]
        if surface == "if":
            assert result.diagnostics[0].details["reason"] == "access_context_differs_between_check_and_run"
    else:
        report = validate_workflow_semantics(workflow, state_base_dir=tmp_path / "a", available_profiles=context["available_profiles"], profile_working_directories=context["profile_working_directories"])
        assert report.ok, report.diagnostics


@pytest.mark.parametrize("mode", MODES)
def test_ignored_switch_does_not_change_storage_identity(tmp_path, context, mode):
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: "b"\n'
        '- name: read\n  publish:\n    value: state.other["key"]',
    )
    workflow = replace(
        load_workflow_text(text), state_bindings={"memory": "store", "other": "store"}, states={"store": "state.json"},
        playbook_owned_pre_run=True, launch_profile_source="explicit_cli", launch_profile_name="a",
    )
    result = mode(workflow, **context)
    assert [d.code for d in result.diagnostics] == [CODE]
    assert result.diagnostics[0].details["storage_path"] == str(tmp_path / "a" / "state.json")


@pytest.mark.parametrize("condition", ('if: "true"', 'if: "false"', 'if: inputs.selected == "b"', 'gate:\n    all:\n      - inputs.selected == "b"'))
def test_static_switch_conditions_do_not_require_observations(tmp_path, context, condition):
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: "b"\n  ' + condition + '\n'
        '- name: read\n  publish:\n    value: state.memory["key"]',
        bindings='inputs:\n  selected: {default: b}\n',
    )
    workflow = replace(load_workflow_text(text), state_bindings={"memory": "store"}, states={"store": "state.json"})
    with patch("subprocess.run", side_effect=AssertionError("unexpected external call")), patch(
        "ordo.runtime.local_expression_engine.core.read_state_document", side_effect=AssertionError("unexpected state read")
    ):
        report = validate_workflow_semantics(workflow, state_base_dir=tmp_path / "a", available_profiles=context["available_profiles"], profile_working_directories=context["profile_working_directories"])
    if condition == 'if: "false"':
        assert [d.code for d in report.diagnostics] == [CODE]
    else:
        assert report.ok, report.diagnostics


def test_profile_input_updates_affect_subsequent_static_switches(tmp_path, context):
    profiles = {"b": Profile(name="b", inputs={"selected": "a"}), "a": Profile(name="a")}
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: "b"\n'
        '- name: switch-back\n  profile_switch: ${inputs.selected}\n'
        '- name: read\n  publish:\n    value: state.memory["key"]',
        bindings='inputs:\n  selected: {default: b}\n',
    )
    workflow = replace(load_workflow_text(text), state_bindings={"memory": "store"}, states={"store": "state.json"})
    report = validate_workflow_semantics(workflow, state_base_dir=tmp_path / "a", available_profiles=profiles, profile_working_directories=context["profile_working_directories"])
    assert [d.code for d in report.diagnostics] == [CODE]


@pytest.mark.parametrize("mode", MODES)
def test_gate_reads_ambient_not_profile_payload_directory(tmp_path, context, mode):
    (tmp_path / "state.json").write_text('{"key": {"value": 7}}')
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: "b"\n'
        '- name: read\n  gate: state.other["key"].value == 7\n  value: ${1}',
    )
    workflow = replace(load_workflow_text(text), state_bindings={"memory": "store", "other": "alias"}, states={"store": str(tmp_path / "b" / "state.json"), "alias": "state.json"})
    result = mode(workflow, **context)
    assert result.status is RuntimeStatus.OK, result.diagnostics


def test_known_violation_takes_precedence_over_later_unknown_context(tmp_path, context):
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: known-read\n  publish:\n    value: state.memory["key"]\n'
        '- name: switch\n  profile_switch: ${state.other["profile"]}\n'
        '- name: unknown-read\n  publish:\n    value: state.memory["key"]',
    )
    workflow = replace(load_workflow_text(text), state_bindings={"memory": "store", "other": "selector"}, states={"store": "state.json", "selector": str(tmp_path / "selector.json")})
    report = validate_workflow_semantics(workflow, state_base_dir=tmp_path / "a", available_profiles=context["available_profiles"], profile_working_directories=context["profile_working_directories"])
    assert [d.code for d in report.diagnostics] == [CODE]
    assert report.diagnostics[0].details["read_path"] == ["blocks", "0", "steps", "1"]


def test_unknown_profile_cannot_obscure_a_fixed_ambient_storage_base(tmp_path, context):
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: ${state.other["profile"]}\n'
        '- name: read\n  publish:\n    value: state.memory["key"]',
    )
    workflow = replace(load_workflow_text(text), state_bindings={"memory": "store", "other": "selector"}, states={"store": "state.json", "selector": str(tmp_path / "selector.json")})
    report = validate_workflow_semantics(workflow, available_profiles=context["available_profiles"])
    assert [d.code for d in report.diagnostics] == [CODE]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("alias", (True, False))
def test_bound_run_target_uses_storage_not_prebinding_role_order(tmp_path, context, mode, alias):
    child = workflow_text(
        '- name: select-initial\n  profile_switch: "a"\n'
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: "b"\n'
        '- name: read\n  publish:\n    value: state.memory["key"]',
    )
    (tmp_path / "child.yml").write_text(child)
    (tmp_path / "parent.yml").write_text(workflow_text(
        ('- name: external\n  uses: shell.command\n  with:\n    command: "must not execute"\n' if alias else '')
        + '- name: child\n  run: child.yml',
        guards="  - guards:\n      - git.worktree.clean\n" if alias else "",
    ))
    workflow = replace(load_workflow_file(tmp_path / "parent.yml"), state_bindings={"memory": "store", "other": "store"}, states={"store": str(tmp_path / "a" / "state.json") if alias else "state.json"})
    if alias:
        probe = Mock(side_effect=AssertionError("unexpected observation"))
        with patch("subprocess.run", side_effect=AssertionError("unexpected external call")):
            result = mode(workflow, **context, guard_probe=probe)
        assert result.status is RuntimeStatus.VALIDATION_ERROR
        assert [d.code for d in result.diagnostics] == [CODE]
        assert result.diagnostics[0].details["source"] == str(tmp_path / "child.yml")
        assert not result.operation_results
        probe.assert_not_called()
    else:
        result = mode(workflow, **context)
        assert result.status is RuntimeStatus.OK, result.diagnostics
