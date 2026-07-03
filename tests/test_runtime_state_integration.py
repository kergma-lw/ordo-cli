import json
import tempfile
import unittest

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import check_workflow, execute_workflow, load_workflow_text, plan_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class RuntimeStateIntegrationTest(unittest.TestCase):
    def test_execute_can_write_read_and_delete_runtime_state_in_one_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            workflow = load_workflow_text(
                f"""
version: 0
workflow: open-task
inputs:
  issue_ref: owner/repo#1
  command: printf integrated-state
states:
  task_state: {state_path}
guards: []
steps:
  - name: remember-command
    state_set:
      states.task_state[inputs.issue_ref].command: ${{inputs.command}}
  - name: run-command
    uses: shell.command
    with:
      command: ${{states.task_state[inputs.issue_ref].command}}
  - name: forget-command
    state_delete: states.task_state[inputs.issue_ref].command
"""
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["executed_steps"], ["remember-command", "run-command", "forget-command"])
            self.assertEqual(result.operation_results[1].observations.get("stdout"), "integrated-state")
            with open(state_path, "r", encoding="utf-8") as handle:
                persisted = json.load(handle)
            self.assertEqual(persisted["values"], {})

    def test_plan_and_check_keep_runtime_state_steps_visible_without_executing_them(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
states:
  task_state: /tmp/task-state.json
guards: []
steps:
  - name: remember-branch
    state_set:
      states.task_state[inputs.issue_ref].branch: ${inputs.branch}
  - name: forget-branch
    state_delete: states.task_state[inputs.issue_ref].branch
"""
        )

        check_result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(check_result.status, RuntimeStatus.OK)
        self.assertEqual(plan_result.status, RuntimeStatus.OK)
        self.assertEqual(plan_result.outputs["step_items"][0]["reference"], "state_set")
        self.assertEqual(plan_result.outputs["step_items"][1]["reference"], "state_delete")
        self.assertEqual(plan_result.outputs["step_items"][0]["eligibility"], "eligible")


if __name__ == "__main__":
    unittest.main()
