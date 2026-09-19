from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ordo.model.profile import Profile
from ordo.model.runtime import RuntimeStatus
from ordo.playbook import PlaybookError, activate_playbook
from ordo.runtime import (
    check_workflow, execute_workflow, assess_workflow_readiness, load_workflow_text,
    plan_workflow, review_workflow, validate_workflow_semantics, validate_workflow_text,
)
from ordo.runtime.nexting import build_next_candidate
from tests.support import STANDARD_CONNECTOR_PROVIDER
from tests.test_state_role_write_order import workflow_text


CODE = "validation.workflow.state_storage.write_before_last_read"
MODES = (check_workflow, review_workflow, plan_workflow, assess_workflow_readiness, execute_workflow)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("mutation", ('state_delete: state.memory["key"]', 'state_set:\n  state.memory["key"]: ${1}'))
@pytest.mark.parametrize("binding", ("same-name", "normalized-path", "hardlink", "missing-binding", "missing-state"))
def test_modes_reject_before_observation_or_effects(tmp_path, mode, mutation, binding):
    state_path = tmp_path / "state.json"
    original = '{"key": {"value": "original"}}'
    state_path.write_text(original)
    text = workflow_text(
        '- name: external\n  uses: shell.command\n  with:\n    command: "must not execute"\n'
        '- name: mutate\n  ' + mutation.replace('\n', '\n  ') + '\n'
        '- name: read\n  publish:\n    value: state.other["different-key"].value',
        guards="  - guards:\n      - git.worktree.clean\n",
    )
    assert validate_workflow_text(text).ok
    states = {"store": str(state_path), "alias": str(tmp_path / "sub" / ".." / "state.json")}
    bindings = {"memory": "store", "other": "store" if binding == "same-name" else "alias"}
    expected = CODE
    if binding == "hardlink":
        alias_path = tmp_path / "alias.json"
        alias_path.hardlink_to(state_path)
        states["alias"] = str(alias_path)
    if binding == "missing-binding":
        del bindings["other"]
        expected = "runtime.state.binding_missing"
    if binding == "missing-state":
        del states["alias"]
        expected = "runtime.state.declaration_missing"
    workflow = replace(load_workflow_text(text), state_bindings=bindings, states=states)
    probe = Mock(side_effect=AssertionError("unexpected observation"))
    executor = Mock(side_effect=AssertionError("unexpected effect"))
    kwargs = {"step_executor": executor} if mode is execute_workflow else {}
    with patch("subprocess.run", side_effect=AssertionError("unexpected external call")), patch(
        "ordo.runtime.local_expression_engine.core.read_state_document", side_effect=AssertionError("unexpected state read")
    ):
        result = mode(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER, **kwargs)
    assert result.status is RuntimeStatus.VALIDATION_ERROR
    assert [d.code for d in result.diagnostics] == [expected]
    assert not result.operation_results
    probe.assert_not_called()
    executor.assert_not_called()
    assert state_path.read_text() == original
    if binding == "hardlink":
        assert alias_path.read_text() == original
        assert alias_path.samefile(state_path)
    diagnostic = result.diagnostics[0]
    if expected == CODE:
        assert diagnostic.path == ("blocks", "1", "steps", "1")
        assert diagnostic.details["read_path"] == ["blocks", "1", "steps", "2"]
        assert diagnostic.details["state_role"] == "memory"
        assert diagnostic.details["read_state_role"] == "other"
        assert diagnostic.details["state"] == "store"
        assert diagnostic.details["read_state"] == bindings["other"]
        assert diagnostic.details["storage_path"] == str(state_path)
    if mode is assess_workflow_readiness:
        with patch("ordo.runtime.resolution.get_default_connector_provider", return_value=STANDARD_CONNECTOR_PROVIDER), patch(
            "ordo.runtime.checking.check_workflow", side_effect=AssertionError("next must not repeat analysis")
        ):
            candidate = build_next_candidate(
                workflow="ordering", description=None, workflow_category=None, when=None,
                working_directory=None, runtime_result=result, runtime_workflow=workflow,
            )
        assert not candidate.allowed
        assert expected in [d.code for d in candidate.diagnostics]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("shape", ("distinct", "read-first", "same-step", "writes-only"))
@pytest.mark.parametrize("hardlink", (False, True))
def test_valid_storage_order_is_not_a_blanket_alias_halt(tmp_path, mode, shape, hardlink):
    read = '- name: read\n  publish:\n    value: state.other["key"].value\n'
    write = '- name: mutate\n  state_delete: state.memory["key"]\n'
    steps = write + read
    if shape == "read-first":
        steps = read + write
    elif shape == "same-step":
        steps = '- name: mutate\n  state_set:\n    state.memory["key"]: state.other["key"]\n'
    elif shape == "writes-only":
        steps = write + '- name: again\n  state_delete: state.other["key"]\n'
    states = {"store": str(tmp_path / "state.json"), "alias": str(tmp_path / ("other.json" if shape == "distinct" else "state.json"))}
    for path in states.values():
        Path(path).write_text('{"key": {"value": "original"}}')
    if hardlink and shape != "distinct":
        alias_path = tmp_path / "alias.json"
        alias_path.hardlink_to(Path(states["store"]))
        states["alias"] = str(alias_path)
    workflow = replace(load_workflow_text(workflow_text(steps)), state_bindings={"memory": "store", "other": "alias"}, states=states)
    result = mode(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.status is RuntimeStatus.OK, result.diagnostics
    if hardlink and shape != "distinct":
        assert alias_path.samefile(Path(states["store"]))
        assert alias_path.read_text() == Path(states["store"]).read_text()


@pytest.mark.parametrize("mode", MODES)
def test_initial_profile_directory_is_the_runtime_relative_path_base(tmp_path, mode):
    text = workflow_text('- name: mutate\n  state_delete: state.memory["key"]\n- name: read\n  publish:\n    value: state.other["key"]')
    workflow = replace(
        load_workflow_text(text), profile="selected",
        state_bindings={"memory": "store", "other": "alias"},
        states={"store": "state.json", "alias": str(tmp_path / "state.json")},
    )
    result = mode(
        workflow, available_profiles={"selected": Profile(name="selected")},
        profile_working_directories={"selected": tmp_path}, connector_provider=STANDARD_CONNECTOR_PROVIDER,
    )
    assert result.status is RuntimeStatus.VALIDATION_ERROR
    assert [d.code for d in result.diagnostics] == [CODE]


def test_symlink_alias_and_cwd_base_use_registry_locations(tmp_path, monkeypatch):
    (tmp_path / "alias.json").symlink_to(tmp_path / "state.json")
    monkeypatch.chdir(tmp_path)
    workflow = replace(
        load_workflow_text(workflow_text('- name: mutate\n  state_delete: state.memory["key"]\n- name: read\n  publish:\n    value: state.other["key"]')),
        state_bindings={"memory": "store", "other": "alias"}, states={"store": "state.json", "alias": "alias.json"},
    )
    report = validate_workflow_semantics(workflow)
    assert [d.code for d in report.diagnostics] == [CODE]
    assert report.diagnostics[0].details["storage_path"] == str(tmp_path / "state.json")
    assert not (tmp_path / "state.json").exists()


def test_invalid_location_is_a_structured_error(tmp_path):
    workflow = replace(
        load_workflow_text(workflow_text('- name: mutate\n  state_delete: state.memory["key"]')),
        state_bindings={"memory": "store"}, states={"store": "bad\0path"},
    )
    report = validate_workflow_semantics(workflow)
    assert report.status is RuntimeStatus.VALIDATION_ERROR
    assert [d.code for d in report.diagnostics] == ["runtime.state.location_invalid"]


@pytest.mark.parametrize("base", ("playbook", "workflow", "profile"))
@pytest.mark.parametrize("mode", MODES)
def test_playbook_resolution_keeps_storage_fixed_across_profile_switch(tmp_path, base, mode):
    (tmp_path / "workflows").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "work").mkdir()
    (tmp_path / "other").mkdir()
    (tmp_path / "profiles" / "selected.yml").write_text("name: selected\nworking_directory: work\n")
    (tmp_path / "profiles" / "other.yml").write_text("name: other\nworking_directory: other\n")
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: switch\n  profile_switch: "other"\n'
        '- name: read\n  publish:\n    value: state.other["key"]',
    )
    (tmp_path / "workflows" / "ordering.yml").write_text(text)
    working_directory = "    working_directory: work\n" if base == "workflow" else ""
    (tmp_path / "ordo.yaml").write_text(
        "version: 1\nworkflows:\n  ordering:\n    file: ordering.yml\n" + working_directory
        + "    state_bindings:\n      memory: store\n      other: alias\n"
        "profiles:\n  selected:\n    file: selected.yml\n  other:\n    file: other.yml\n"
        "states:\n  store:\n    path: state.json\n  alias:\n    path: sub/../state.json\n"
    )
    with pytest.raises(PlaybookError) as error:
        activate_playbook(
            workflow_name="ordering", profile_name="selected" if base == "profile" else None,
            playbook_path=tmp_path / "ordo.yaml", cwd=tmp_path,
        )
    expected = tmp_path / ("state.json" if base == "playbook" else "work/state.json")
    assert [d.code for d in error.value.diagnostics] == [CODE]
    assert error.value.diagnostics[0].details["storage_path"] == str(expected)
    (tmp_path / "workflows" / "ordering.yml").write_text(workflow_text(
        '- name: switch\n  profile_switch: "other"\n'
        '- name: read\n  publish:\n    value: state.other["key"]\n'
        '- name: mutate\n  state_delete: state.memory["key"]',
    ))
    activated = activate_playbook(
        workflow_name="ordering", profile_name="selected" if base == "profile" else None,
        playbook_path=tmp_path / "ordo.yaml", cwd=tmp_path,
    )
    assert activated.workflow.states == {"store": str(expected), "alias": str(expected)}
    result = mode(
        replace(activated.workflow, blocks=load_workflow_text(text).blocks),
        profile=activated.profile, available_profiles=activated.available_profiles,
        profile_working_directories=activated.profile_working_directories,
        connector_provider=STANDARD_CONNECTOR_PROVIDER,
    )
    assert result.status is RuntimeStatus.VALIDATION_ERROR
    assert [d.code for d in result.diagnostics] == [CODE]
    assert result.diagnostics[0].details["storage_path"] == str(expected)


def test_alias_reads_in_later_guards_expand_let(tmp_path):
    text = workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]',
        bindings='let:\n  saved: state.other["different-key"]\n',
    ) + '  - guards:\n      - saved.value == "yes"\n'
    workflow = replace(load_workflow_text(text), state_bindings={"memory": "store", "other": "store"}, states={"store": str(tmp_path / "state.json")})
    report = validate_workflow_semantics(workflow)
    assert [d.code for d in report.diagnostics] == [CODE]
    assert report.diagnostics[0].details["read_path"] == ["blocks", "1", "guards", "0"]


@pytest.mark.parametrize("reverse_declarations", (False, True))
@pytest.mark.parametrize("identity", ("hardlink", "missing-alias", "missing-distinct", "different-device"))
def test_storage_identity_grouping_is_stable(tmp_path, reverse_declarations, identity):
    writer = tmp_path / "writer.json"
    reader = tmp_path / "reader.json"
    if identity == "hardlink":
        writer.write_text("{}")
        reader.hardlink_to(writer)
    elif identity == "missing-alias":
        reader = tmp_path / "sub" / ".." / "writer.json"
    states = {"writer": str(writer), "reader": str(reader)}
    if reverse_declarations:
        states = dict(reversed(states.items()))
    workflow = replace(
        load_workflow_text(workflow_text(
            '- name: mutate\n  state_delete: state.memory["key"]\n'
            '- name: read\n  publish:\n    value: state.other["key"]'
        )),
        state_bindings={"memory": "writer", "other": "reader"}, states=states,
    )
    if identity == "different-device":
        with patch.object(Path, "stat", new=lambda path: SimpleNamespace(st_dev=1 if path == writer else 2, st_ino=42)):
            report = validate_workflow_semantics(workflow)
    else:
        report = validate_workflow_semantics(workflow)
    if identity in {"hardlink", "missing-alias"}:
        assert [d.code for d in report.diagnostics] == [CODE]
        assert report.diagnostics[0].details["storage_path"] == str(writer)
    else:
        assert report.ok, report.diagnostics


def test_storage_stat_failure_is_not_treated_as_a_missing_file(tmp_path):
    workflow = replace(
        load_workflow_text(workflow_text('- name: mutate\n  state_delete: state.memory["key"]')),
        state_bindings={"memory": "store"}, states={"store": str(tmp_path / "state.json")},
    )
    with patch.object(Path, "stat", side_effect=PermissionError("stat denied")):
        report = validate_workflow_semantics(workflow)
    assert [d.code for d in report.diagnostics] == ["runtime.state.location_invalid"]
