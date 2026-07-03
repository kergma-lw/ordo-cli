import json
import tempfile
import unittest

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import execute_workflow, load_workflow_text

from tests.support import STANDARD_CONNECTOR_PROVIDER


class RuntimeValueResolutionTest(unittest.TestCase):
    def test_execute_resolves_state_reference_in_step_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "version": 1,
                        "values": {"owner/repo#1": {"command": "printf resolved-from-state"}},
                    },
                    handle,
                )

            workflow = load_workflow_text(
                f"""
version: 0
workflow: open-task
inputs:
  issue_ref: owner/repo#1
states:
  task_state: {state_path}
guards: []
steps:
  - name: run-command
    uses: shell.command
    with:
      command: ${{states.task_state[inputs.issue_ref].command}}
"""
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.operation_results[0].status, "ok")
            self.assertEqual(result.operation_results[0].observations.get("stdout"), "resolved-from-state")

    def test_execute_reports_missing_state_value_as_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "values": {}}, handle)

            workflow = load_workflow_text(
                f"""
version: 0
workflow: open-task
inputs:
  issue_ref: owner/repo#1
states:
  task_state: {state_path}
guards: []
steps:
  - name: run-command
    uses: shell.command
    with:
      command: ${{states.task_state[inputs.issue_ref].command}}
"""
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
            self.assertEqual(result.operation_results[0].status, "input_error")
            self.assertEqual(result.operation_results[0].diagnostics[0].code, "runtime.value.state_missing")

    def test_execute_resolves_format_expression_in_step_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  type: Task
  issue_number: 7
  title: Hello World
guards: []
steps:
  - name: run-command
    uses: shell.command
    with:
      command: ${format("printf {}", format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug))}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].status, "ok")
        self.assertEqual(result.operation_results[0].observations.get("stdout"), "task/7-hello-world")

    def test_execute_resolves_yaml_format_object_in_step_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  type: Task
  issue_number: 7
  title: Hello World
guards: []
steps:
  - name: run-command
    uses: shell.command
    with:
      command:
        format: "printf {}"
        args:
          -
            format: "{}/{}-{}"
            args:
              - ${inputs.type | lower}
              - ${inputs.issue_number}
              - ${inputs.title | slug}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].status, "ok")
        self.assertEqual(result.operation_results[0].observations.get("stdout"), "task/7-hello-world")


if __name__ == "__main__":
    unittest.main()
