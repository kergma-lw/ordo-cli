import json
import tempfile
import unittest
from unittest.mock import patch

from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Workflow
from ordo.runtime import check_workflow, execute_workflow, load_workflow_text, plan_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class RuntimeStateExecutionTest(unittest.TestCase):
    @staticmethod
    def _completed(*, returncode: int, stdout: str, stderr: str = ""):
        import subprocess

        return subprocess.CompletedProcess(args=["cmd"], returncode=returncode, stdout=stdout, stderr=stderr)

    def test_check_allows_guard_expression_to_read_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump({"owner/repo": {"branch": "feature/1"}}, handle)
            workflow = load_workflow_text(
                """
version: 0
workflow: close-task
inputs:
  repository: owner/repo
state_needs:
  task_memory: {}
blocks:
  - guards:
      - state.task_memory[inputs.repository].branch == "feature/1"
  - steps: []
"""
            )
            workflow = Workflow(
                version=workflow.version,
                workflow=workflow.workflow,
                inputs=workflow.inputs,
                declared_inputs=workflow.declared_inputs,
                state_needs=workflow.state_needs,
                state_bindings={"task_memory": "repo_task_state"},
                states={"repo_task_state": state_path},
                guards=workflow.guards,
                steps=workflow.steps,
            )

            result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)

    def test_execute_runs_state_set_and_state_delete_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            workflow = load_workflow_text(
                f"""
version: 0
workflow: open-task
inputs:
  issue_ref: owner/repo#1
  branch: feature/1
state_needs:
  task_memory: {{}}
blocks:
  - guards: []
  - steps:
      - name: remember-branch
        state_set:
          state.task_memory[inputs.issue_ref].branch: ${{inputs.branch}}
      - name: forget-branch
        state_delete: state.task_memory[inputs.issue_ref].branch
"""
            )
            workflow = Workflow(
                version=workflow.version,
                workflow=workflow.workflow,
                inputs=workflow.inputs,
                declared_inputs=workflow.declared_inputs,
                state_needs=workflow.state_needs,
                state_bindings={"task_memory": "repo_task_state"},
                states={"repo_task_state": state_path},
                guards=workflow.guards,
                steps=workflow.steps,
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.operation_results[0].status, "ok")
            self.assertEqual(result.operation_results[1].outputs.get("deleted"), True)
            with open(state_path, "r", encoding="utf-8") as handle:
                persisted = json.load(handle)
            self.assertEqual(persisted, {})

    def test_execute_state_set_allows_dynamic_key_expression_from_prior_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            workflow = load_workflow_text(
                f"""
version: 0
workflow: open-task
inputs:
  issue_ref: owner/repo#1
  branch: feature/1
state_needs:
  task_memory: {{}}
blocks:
  - guards: []
  - steps:
      - name: choose-key
        value: ${{inputs.issue_ref}}
        register: chosen
      - name: remember-branch
        state_set:
          state.task_memory[step.chosen.outputs.value].branch: ${{inputs.branch}}
"""
            )
            workflow = Workflow(
                version=workflow.version,
                workflow=workflow.workflow,
                inputs=workflow.inputs,
                declared_inputs=workflow.declared_inputs,
                state_needs=workflow.state_needs,
                state_bindings={"task_memory": "repo_task_state"},
                states={"repo_task_state": state_path},
                guards=workflow.guards,
                steps=workflow.steps,
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            with open(state_path, "r", encoding="utf-8") as handle:
                persisted = json.load(handle)
            self.assertEqual(persisted, {"owner/repo#1": {"branch": "feature/1"}})

    def test_execute_state_set_allows_probe_reference_in_value_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            workflow = load_workflow_text(
                """
version: 0
workflow: open-task
inputs:
  issue_ref: owner/repo#1
state_needs:
  task_memory: {}
blocks:
  - guards: []
  - steps:
      - name: remember-branch
        state_set:
          state.task_memory[inputs.issue_ref].branch: git.branch.value
"""
            )
            workflow = Workflow(
                version=workflow.version,
                workflow=workflow.workflow,
                inputs=workflow.inputs,
                declared_inputs=workflow.declared_inputs,
                state_needs=workflow.state_needs,
                state_bindings={"task_memory": "repo_task_state"},
                states={"repo_task_state": state_path},
                guards=workflow.guards,
                steps=workflow.steps,
            )

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                    self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                ]

                result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            with open(state_path, "r", encoding="utf-8") as handle:
                persisted = json.load(handle)
            self.assertEqual(persisted, {"owner/repo#1": {"branch": "feature/demo"}})

    def test_execute_reports_state_mutation_failures_structurally(self) -> None:
        loaded = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  issue_ref: {}
  branch: {}
state_needs:
  task_memory: {}
blocks:
  - guards: []
  - steps:
      - name: remember-branch
        state_set:
          state.task_memory[inputs.issue_ref].branch: ${inputs.branch}
"""
        )
        workflow = Workflow(
            version=loaded.version,
            workflow=loaded.workflow,
            inputs={},
            declared_inputs=loaded.declared_inputs,
            state_needs=loaded.state_needs,
            state_bindings={"task_memory": "repo_task_state"},
            states={"repo_task_state": ".ordo/task-state.json"},
            guards=loaded.guards,
            steps=loaded.steps,
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.operation_results[0].status, "state_error")
        self.assertEqual(result.operation_results[0].diagnostics[0].code, "runtime.state.input_missing")

    def test_execute_state_set_rejects_unknown_bare_object_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            workflow = load_workflow_text(
                """
version: 0
workflow: open-task
inputs:
  issue_ref: owner/repo#1
state_needs:
  task_memory: {}
blocks:
  - guards: []
  - steps:
      - name: remember-profile
        state_set:
          state.task_memory[inputs.issue_ref].profile: meta
"""
            )
            workflow = Workflow(
                version=workflow.version,
                workflow=workflow.workflow,
                inputs=workflow.inputs,
                declared_inputs=workflow.declared_inputs,
                state_needs=workflow.state_needs,
                state_bindings={"task_memory": "repo_task_state"},
                states={"repo_task_state": state_path},
                guards=workflow.guards,
                steps=workflow.steps,
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
            self.assertEqual(result.operation_results[0].status, "state_error")
            self.assertEqual(result.operation_results[0].diagnostics[0].code, "runtime.value.reference_unknown")

    def test_execute_state_set_rejects_null_key_expression(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  branch: feature/1
state_needs:
  task_memory: {}
blocks:
  - guards: []
  - steps:
      - name: remember-branch
        state_set:
          state.task_memory[null].branch: ${inputs.branch}
"""
        )
        workflow = Workflow(
            version=workflow.version,
            workflow=workflow.workflow,
            inputs=workflow.inputs,
            declared_inputs=workflow.declared_inputs,
            state_needs=workflow.state_needs,
            state_bindings={"task_memory": "repo_task_state"},
            states={"repo_task_state": "/tmp/task-state.json"},
            guards=workflow.guards,
            steps=workflow.steps,
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "validation.workflow.state_path.key_expr.result_type")

    def test_plan_marks_builtin_state_steps_as_effectful(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  issue_ref: {}
  branch: {}
state_needs:
  task_memory: {}
blocks:
  - guards: []
  - steps:
      - name: remember-branch
        state_set:
          state.task_memory[inputs.issue_ref].branch: ${inputs.branch}
"""
        )
        workflow = Workflow(
            version=workflow.version,
            workflow=workflow.workflow,
            inputs=workflow.inputs,
            declared_inputs=workflow.declared_inputs,
            state_needs=workflow.state_needs,
            state_bindings={"task_memory": "repo_task_state"},
            states={"repo_task_state": "/tmp/task-state.json"},
            guards=workflow.guards,
            steps=workflow.steps,
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["step_items"][0]["reference"], "state_set")
        self.assertEqual(result.outputs["step_items"][0]["kind"], "builtin")
        self.assertEqual(result.outputs["step_items"][0]["effect"], "effectful")


if __name__ == "__main__":
    unittest.main()
