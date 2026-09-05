from dataclasses import replace
from unittest.mock import patch

import pytest

from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Step, StepBlock, Workflow
from ordo.runtime import LoadError, execute_workflow, load_workflow_file, load_workflow_text, validate_workflow_semantics
from ordo.runtime.fragment_runs import materialize_run_workflow
from ordo.runtime import validation
from tests.support import STANDARD_CONNECTOR_PROVIDER
from tests.test_state_role_write_order import workflow_text
from tests.test_state_storage_write_order import CODE


@pytest.mark.parametrize("body", ('- name: read\n  publish:\n    value: ${state.memory["key"]}', '- name: write\n  state_delete: state.memory["key"]'))
def test_run_state_surface_is_supported_but_include_stays_forbidden(tmp_path, body):
    target = tmp_path / "child.yml"
    target.write_text("steps:\n" + ''.join('  ' + line + '\n' for line in body.splitlines()))
    caller = replace(load_workflow_text(workflow_text('- name: child\n  run: child.yml')),
                     state_bindings={"memory": "store"}, states={"store": str(tmp_path / "state.json")})
    step = replace(caller.steps[0], resolved_run_path=str(target))
    child = materialize_run_workflow(step, caller, block_index=0, step_index=0)
    assert isinstance(child, Workflow), child
    (tmp_path / "include.yml").write_text("version: 0\nworkflow: included\nblocks:\n  - include: child.yml\n")
    with pytest.raises(LoadError) as error:
        load_workflow_file(tmp_path / "include.yml")
    assert error.value.diagnostics[0].code == "load.workflow.include.state_forbidden"


@pytest.mark.parametrize("override", ("run_state_bindings", "run_states"))
@pytest.mark.parametrize("inline", (False, True))
def test_each_invocation_is_validated_with_its_own_state_bindings(tmp_path, override, inline):
    target = tmp_path / "child.yml"
    target.write_text(workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: read\n  publish:\n    value: state.other["key"]'
    ))
    distinct = {"writer": str(tmp_path / "one.json"), "reader": str(tmp_path / "two.json")}
    first = Step(name="first", run="child.yml", resolved_run_path=str(target))
    overrides = {"run_state_bindings": {"other": "writer"}} if override == "run_state_bindings" else {"run_states": {"reader": distinct["writer"]}}
    second = replace(first, name="second", **overrides)
    steps = (first, second)
    if inline:
        steps = (Step(name="inline", for_each="${[1]}", steps=steps),)
    workflow = Workflow(version=0, workflow="parent", state_needs={"memory": {}, "other": {}}, state_bindings={"memory": "writer", "other": "reader"}, states=distinct, blocks=(StepBlock(steps=steps),))
    report = validate_workflow_semantics(workflow)
    assert [d.code for d in report.diagnostics] == [CODE], report.diagnostics
    assert report.diagnostics[0].details["source"] == str(target)
    assert report.diagnostics[0].details["read_state"] == ("writer" if override == "run_state_bindings" else "reader")


def test_named_run_inside_inline_is_checked_before_outer_effects(tmp_path):
    target = tmp_path / "child.yml"
    target.write_text(workflow_text(
        '- name: mutate\n  state_delete: state.memory["key"]\n'
        '- name: read\n  publish:\n    value: state.other["key"]'
    ))
    parent = tmp_path / "parent.yml"
    parent.write_text(workflow_text(
        '- name: external\n  uses: shell.command\n  with:\n    command: "must not execute"\n'
        '- name: inline\n  for_each: ${[1]}\n  steps:\n    - name: child\n      run: child.yml'
    ))
    workflow = replace(load_workflow_file(parent), state_bindings={"memory": "store", "other": "store"}, states={"store": str(tmp_path / "state.json")})
    with patch("subprocess.run", side_effect=AssertionError("unexpected external effect")):
        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.status is RuntimeStatus.VALIDATION_ERROR
    assert CODE in [d.code for d in result.diagnostics]


def test_forbidden_include_in_inline_named_target_is_rejected_before_effects(tmp_path):
    (tmp_path / "forbidden.yml").write_text('steps:\n  - name: mutate\n    state_delete: state.memory["key"]\n')
    (tmp_path / "child.yml").write_text('version: 0\nworkflow: child\nblocks:\n  - include: forbidden.yml\n')
    parent = tmp_path / "parent.yml"
    parent.write_text(workflow_text(
        '- name: external\n  uses: shell.command\n  with:\n    command: "must not execute"\n'
        '- name: inline\n  for_each: ${[1]}\n  steps:\n    - name: child\n      run: child.yml'
    ))
    workflow = load_workflow_file(parent)
    with patch("subprocess.run", side_effect=AssertionError("unexpected external call")):
        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.status is RuntimeStatus.VALIDATION_ERROR
    assert [d.code for d in result.diagnostics] == ["load.workflow.include.state_forbidden"]
    assert not result.operation_results


def test_active_recursion_stack_terminates_without_global_filename_skipping(tmp_path):
    (tmp_path / "a.yml").write_text(workflow_text('- name: next\n  run: b.yml'))
    (tmp_path / "b.yml").write_text(workflow_text('- name: next\n  run: a.yml'))
    workflow = load_workflow_file(tmp_path / "a.yml")
    with patch.object(validation, "_load_run_target_workflow_for_validation", wraps=validation._load_run_target_workflow_for_validation) as load:
        validate_workflow_semantics(workflow)
    # Only the existing reusable-target pass loads named targets; local storage checks do not.
    assert load.call_count == 1


@pytest.mark.parametrize("child_writes", (False, True))
def test_named_target_accesses_are_not_merged_into_caller_order(tmp_path, child_writes):
    write = '- name: mutate\n  state_delete: state.memory["key"]\n'
    read = '- name: read\n  publish:\n    value: state.other["key"]\n'
    (tmp_path / "child.yml").write_text(workflow_text(write if child_writes else read))
    parent = tmp_path / "parent.yml"
    run = '- name: child\n  run: child.yml\n'
    parent.write_text(workflow_text(run + read if child_writes else write + run))
    workflow = replace(load_workflow_file(parent), state_bindings={"memory": "store", "other": "store"}, states={"store": str(tmp_path / "state.json")})
    with patch.object(validation, "_load_run_target_workflow_for_validation", wraps=validation._load_run_target_workflow_for_validation) as load:
        report = validate_workflow_semantics(workflow)
    # Cross-invocation ordering is deliberately deferred; this does not certify execution safety.
    assert report.ok, report.diagnostics
    assert load.call_count == 1


@pytest.mark.parametrize("inline", (False, True))
def test_general_reusable_target_input_validation_is_preserved(tmp_path, inline):
    child = tmp_path / "child.yml"
    child.write_text(workflow_text(
        '- name: read\n  value: ${inputs.undeclared}',
        bindings='inputs:\n  declared: {}\n',
    ))
    run = '- name: child\n  run: child.yml\n'
    if inline:
        run = '- name: inline\n  for_each: ${[1]}\n  steps:\n' + ''.join('    ' + line for line in run.splitlines(keepends=True))
    parent = tmp_path / "parent.yml"
    parent.write_text(workflow_text(run))
    report = validate_workflow_semantics(load_workflow_file(parent))
    assert report.status is RuntimeStatus.VALIDATION_ERROR
    assert [d.code for d in report.diagnostics] == ["validation.workflow.inputs.undeclared_reference"]
    assert report.diagnostics[0].details["source"] == str(child)
