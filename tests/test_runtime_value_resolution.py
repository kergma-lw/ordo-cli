import json
import tempfile
import unittest

from ordo.model.runtime import OperationResult
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Workflow
from ordo.runtime import execute_workflow, load_workflow_text
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value

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
state_needs:
  task_memory: {{}}
blocks:
  - guards: []
  - steps:
      - name: run-command
        uses: shell.command
        with:
          command: ${{state.task_memory[inputs.issue_ref].command}}
"""
            )
            workflow = Workflow(
                version=workflow.version,
                workflow=workflow.workflow,
                inputs=workflow.inputs,
                state_needs=workflow.state_needs,
                state_bindings={"task_memory": "repo_task_state"},
                states={"repo_task_state": state_path},
                guards=workflow.guards,
                steps=workflow.steps,
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.operation_results[0].status, "ok")
            self.assertEqual(result.operation_results[0].outputs.get("stdout"), "resolved-from-state")

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
state_needs:
  task_memory: {{}}
blocks:
  - guards: []
  - steps:
      - name: run-command
        uses: shell.command
        with:
          command: ${{state.task_memory[inputs.issue_ref].command}}
"""
            )
            workflow = Workflow(
                version=workflow.version,
                workflow=workflow.workflow,
                inputs=workflow.inputs,
                state_needs=workflow.state_needs,
                state_bindings={"task_memory": "repo_task_state"},
                states={"repo_task_state": state_path},
                guards=workflow.guards,
                steps=workflow.steps,
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
blocks:
  - guards: []
  - steps:
      - name: run-command
        uses: shell.command
        with:
          command: ${format("printf {}", format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug))}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].status, "ok")
        self.assertEqual(result.operation_results[0].outputs.get("stdout"), "task/7-hello-world")

    def test_execute_resolves_yaml_format_object_in_step_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  type: Task
  issue_number: 7
  title: Hello World
blocks:
  - guards: []
  - steps:
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
        self.assertEqual(result.operation_results[0].outputs.get("stdout"), "task/7-hello-world")

    def test_execute_resolves_registered_step_output_in_later_step_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
blocks:
  - guards: []
  - steps:
      - name: inspect
        uses: shell.command
        register: first
        with:
          command: printf hello
      - name: replay
        uses: shell.command
        with:
          command: ${format("printf {}", step.first.outputs.stdout)}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].outputs.get("stdout"), "hello")
        self.assertEqual(result.operation_results[1].outputs.get("stdout"), "hello")

    def test_execute_materializes_value_step_output_for_later_step(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  type: Task
  issue_number: 7
  title: Hello World
blocks:
  - guards: []
  - steps:
      - name: compute-branch
        value:
          format: "{}/{}-{}"
          args:
            - ${inputs.type | lower}
            - ${inputs.issue_number}
            - ${inputs.title | slug}
        register: branch
      - name: replay
        uses: shell.command
        with:
          command: ${format("printf {}", step.branch.outputs.value)}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].outputs.get("value"), "task/7-hello-world")
        self.assertEqual(result.operation_results[1].outputs.get("stdout"), "task/7-hello-world")

    def test_execute_resolves_registered_step_output_in_later_step_block(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
blocks:
  - guards: []
  - steps:
      - name: inspect
        uses: shell.command
        register: first
        with:
          command: printf hello
  - guards: []
  - steps:
      - name: replay
        uses: shell.command
        with:
          command: ${format("printf {}", step.first.outputs.stdout)}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].outputs.get("stdout"), "hello")
        self.assertEqual(result.operation_results[1].outputs.get("stdout"), "hello")

    def test_resolve_runtime_value_reads_registered_step_outputs(self) -> None:
        workflow = load_workflow_text("version: 0\nworkflow: demo\nblocks:\n  - guards: []\n  - steps: []\n")

        value = resolve_runtime_value(
            "${step.issue.outputs.id}",
            workflow,
            step_results={"issue": OperationResult(status="ok", summary="inspected", outputs={"id": 17})},
        )

        self.assertEqual(value, 17)

    def test_resolve_runtime_value_reports_missing_registered_step(self) -> None:
        workflow = load_workflow_text("version: 0\nworkflow: demo\nblocks:\n  - guards: []\n  - steps: []\n")

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value("${step.issue.outputs.id}", workflow)

        self.assertEqual(context.exception.code, "runtime.value.step_missing")


if __name__ == "__main__":
    unittest.main()
