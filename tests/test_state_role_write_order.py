import tempfile
import textwrap
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import (
    check_workflow,
    execute_workflow,
    explain_workflow,
    load_workflow_text,
    plan_workflow,
    review_workflow,
    validate_workflow_text,
)
from ordo.runtime.nexting import build_next_candidate
from ordo.runtime import validation

from tests.support import STANDARD_CONNECTOR_PROVIDER


CODE = "validation.workflow.state_role.write_before_last_read"


def workflow_text(steps: str, *, guards: str = "", bindings: str = "") -> str:
    return (
        "version: 0\nworkflow: ordering\n"
        "state_needs:\n  memory: {}\n  other: {}\n"
        + bindings
        + "blocks:\n"
        + guards
        + "  - steps:\n"
        + textwrap.indent(textwrap.dedent(steps).strip(), "      ")
        + "\n"
    )


class StateRoleWriteOrderTest(unittest.TestCase):
    def test_later_read_surfaces_reject_both_mutations(self) -> None:
        readers = {
            "plain_value": 'value: state.memory["different-key"].value\nregister: observed',
            "embedded_value": 'value: ${state.memory["key"].value}\nregister: observed',
            "let_value": "value: saved.value\nregister: observed",
            "profile_switch": "profile_switch: ${saved.value}",
            "publish": 'publish:\n  answer: state.memory["key"].value',
            "result": "result:\n  answer: saved.value",
            "with": 'uses: shell.command\nwith:\n  command: state.memory["key"].value',
            "run_with": "run: fragment.yml\nwith:\n  answer: saved.value",
            "for_each": "run: fragment.yml\nfor_each: saved.items",
            "inline_body": 'for_each: ${[1]}\nsteps:\n  - name: nested\n    publish:\n      answer: state.memory["key"].value',
            "if": 'if:\n  any:\n    - saved.value == "yes"\nvalue: ${1}\nregister: observed',
            "gate": 'gate:\n  all:\n    - saved.value == "yes"\nvalue: ${1}',
            "gate_on_fail": 'gate:\n  all:\n    - git.worktree.clean\n  on_fail:\n    detail: saved.value\nvalue: ${1}',
            "set_key": 'state_set:\n  state.other[state.memory["key"].value]: ${1}',
            "delete_key": 'state_delete: state.other[saved.value]',
            "set_value": 'state_set:\n  state.other["key"]: saved.value',
            "format_args": 'publish:\n  answer:\n    format: "value: {}"\n    args:\n      - saved.value',
            "filter_argument": 'value: ${"yes" | eq(state.memory["key"].value)}\nregister: observed',
            "probe_argument": 'value: gh.issue(repository="owner/repo", issue_number=state.memory["key"].number).exists\nregister: observed',
            "object_list": 'publish:\n  answer: ${[{value:state.memory["key"].value}]}',
            "only_predicate": 'value: ${[] | only(value = state.memory["key"].value)}\nregister: observed',
            "adapter_binding": 'value: json[".value"] with{root:state.memory["key"].value}\nregister: observed',
            "builtin": 'value: ${format("{}", saved.value)}\nregister: observed',
            "unary": 'if: not (saved.value == "yes")\nvalue: ${1}',
        }
        bindings = 'let:\n  saved: state.memory["key"]\n'
        for name, reader in readers.items():
            later = "- name: read\n" + textwrap.indent(reader, "  ")
            with self.subTest(surface=name, mutation="none"):
                report = validate_workflow_text(workflow_text(later, bindings=bindings))
                self.assertEqual(report.status, RuntimeStatus.OK, report.diagnostics)
            for mutation in ('state_set:\n  state.memory["key"]: ${1}', 'state_delete: state.memory["key"]'):
                with self.subTest(surface=name, mutation=mutation):
                    steps = "- name: mutate\n" + textwrap.indent(mutation, "  ") + "\n" + later
                    report = validate_workflow_text(workflow_text(steps, bindings=bindings))
                    self.assertEqual([item.code for item in report.diagnostics], [CODE])
                    self.assertEqual(report.diagnostics[0].path, ("blocks", "0", "steps", "0"))
                    self.assertEqual(report.diagnostics[0].details["state_role"], "memory")

    def test_same_step_reads_other_roles_and_independent_guards_remain_valid(self) -> None:
        text = workflow_text(
            """
            - name: mutate
              if: state.memory["key"].enabled == true
              state_set:
                state.memory[state.memory["key"].key]: state.memory["key"].value
            - name: read-other
              publish:
                value: state.other["key"].value
                literal: 'state.memory["key"].value'
                template:
                  format: 'state.memory["key"] {}'
                  args: ["literal"]
            - name: delete
              state_delete: state.memory[state.memory["key"].key]
            """
        )
        # The delete key is a later read, even though the delete itself can read before writing.
        self.assertIn(CODE, [item.code for item in validate_workflow_text(text).diagnostics])
        text = text[:text.index("      - name: delete")]
        text += "  - guards:\n      - git.worktree.clean\n"
        report = validate_workflow_text(text)
        self.assertEqual(report.status, RuntimeStatus.OK, report.diagnostics)
        report = validate_workflow_text(workflow_text('- name: delete\n  state_delete: state.memory[state.memory["key"].key]'))
        self.assertEqual(report.status, RuntimeStatus.OK, report.diagnostics)

    def test_nested_write_is_ordered_before_later_outer_read(self) -> None:
        report = validate_workflow_text(workflow_text('''
            - name: repeat
              for_each: ${[1]}
              steps:
                - name: mutate
                  state_delete: state.memory["key"]
            - name: later
              publish:
                value: state.memory["key"].value
        '''))
        self.assertEqual([item.code for item in report.diagnostics], [CODE])
        self.assertEqual(report.diagnostics[0].path, ("blocks", "0", "steps", "0", "steps", "0"))

    def test_later_guard_reads_expand_let_and_probe_arguments(self) -> None:
        for guard in ('saved.value == "yes"', 'gh.issue(repository="owner/repo", issue_number=state.memory["key"].number).exists'):
            with self.subTest(guard=guard):
                text = workflow_text('- name: mutate\n  state_delete: state.memory["key"]', bindings='let:\n  saved: state.memory["key"]\n')
                text += "  - guards:\n      - " + guard + "\n"
                self.assertEqual([item.code for item in validate_workflow_text(text).diagnostics], [CODE])

    def test_unused_let_is_not_a_read_and_invalid_cycles_terminate(self) -> None:
        steps = '- name: mutate\n  state_delete: state.memory["key"]'
        report = validate_workflow_text(workflow_text(steps, bindings='let:\n  saved: state.memory["key"]\n'))
        self.assertEqual(report.status, RuntimeStatus.OK, report.diagnostics)
        report = validate_workflow_text(workflow_text(steps + '\n- name: read\n  publish:\n    value: first', bindings='let:\n  first: second\n  second: first\n'))
        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertIn("validation.workflow.let.binding_chain", [item.code for item in report.diagnostics])

    def test_role_collection_memoizes_indirect_let_expansion(self) -> None:
        # Exercise the collector alone: declaration validation still rejects let chains.
        payload = validation.load_yaml_document(workflow_text(
            '- name: mutate\n  state_delete: state.memory["key"]\n'
            '- name: read\n  publish:\n    first: alias.value\n    second: alias.value',
            bindings='let:\n  saved: state.memory["key"]\n  alias: saved\n',
        ))
        with patch.object(validation, "parse_local_expression", wraps=validation.parse_local_expression) as parse:
            diagnostics = validation._validate_state_role_write_order(payload, source="<test>")
        self.assertEqual([item.code for item in diagnostics], [CODE])
        self.assertEqual([call.args[0] for call in parse.call_args_list], ["saved", 'state.memory["key"]'])

    def test_modes_reject_before_any_steps_or_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text('{"key": {"value": "original"}}', encoding="utf-8")
            workflow = load_workflow_text(workflow_text('''
                - name: external-side-effect
                  uses: shell.command
                  with:
                    command: "must not execute"
                - name: mutate
                  state_delete: state.memory["key"]
                - name: read
                  publish:
                    value: state.memory["key"].value
            ''', guards="  - guards:\n      - git.worktree.clean\n"))
            workflow = replace(workflow, state_bindings={"memory": "store"}, states={"store": str(state_path)})
            for mode in (check_workflow, review_workflow, plan_workflow, explain_workflow, execute_workflow):
                with self.subTest(mode=mode.__name__):
                    probe = Mock(side_effect=AssertionError("unexpected observation"))
                    executor = Mock(side_effect=AssertionError("unexpected step"))
                    kwargs = {"step_executor": executor} if mode is execute_workflow else {}
                    with patch("subprocess.run", side_effect=AssertionError("unexpected external call")) as subprocess_run:
                        result = mode(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER, **kwargs)
                    self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
                    self.assertIn("validation.workflow.state_storage.write_before_last_read", [item.code for item in result.diagnostics])
                    self.assertFalse(result.operation_results)
                    probe.assert_not_called()
                    executor.assert_not_called()
                    subprocess_run.assert_not_called()
                    self.assertEqual(state_path.read_text(encoding="utf-8"), '{"key": {"value": "original"}}')
                    if mode is explain_workflow:
                        with patch("ordo.runtime.resolution.get_default_connector_provider", return_value=STANDARD_CONNECTOR_PROVIDER), patch("subprocess.run", side_effect=AssertionError("unexpected external call")):
                            candidate = build_next_candidate(workflow="ordering", description=None, workflow_category=None, when=None, working_directory=None, runtime_result=result, runtime_workflow=workflow)
                        self.assertFalse(candidate.allowed)
                        self.assertIn("validation.workflow.state_storage.write_before_last_read", [item.code for item in candidate.diagnostics])
