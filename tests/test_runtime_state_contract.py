import unittest

from ordo.runtime import load_workflow_text, validate_workflow_text


class RuntimeStateContractTest(unittest.TestCase):
    def test_workflow_loads_named_states_mapping(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
states:
  task_state: .ordo/task-state.json
guards: []
steps: []
"""
        )

        self.assertEqual(workflow.states, {"task_state": ".ordo/task-state.json"})

    def test_workflow_validation_accepts_states_mapping(self) -> None:
        report = validate_workflow_text(
            """
version: 0
workflow: open-task
states:
  task_state: .ordo/task-state.json
guards: []
steps: []
"""
        )

        self.assertEqual(report.status.value, "ok")
        self.assertEqual(report.diagnostics, ())

    def test_workflow_validation_rejects_non_object_states(self) -> None:
        report = validate_workflow_text(
            """
version: 0
workflow: open-task
states: []
guards: []
steps: []
"""
        )

        self.assertEqual(report.status.value, "validation_error")
        self.assertEqual(report.diagnostics[0].code, "validation.states.type")
        self.assertEqual(report.diagnostics[0].path, ("states",))

    def test_workflow_loads_builtin_state_mutation_steps(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
guards: []
steps:
  - name: remember-branch
    state_set:
      states.task_state[inputs.issue_ref].branch: ${inputs.branch}
  - name: forget-branch
    state_delete: states.task_state[inputs.issue_ref].branch
"""
        )

        self.assertEqual(
            workflow.steps[0].state_set,
            {"states.task_state[inputs.issue_ref].branch": "${inputs.branch}"},
        )
        self.assertEqual(workflow.steps[1].state_delete, "states.task_state[inputs.issue_ref].branch")

    def test_workflow_validation_accepts_builtin_state_mutation_steps(self) -> None:
        report = validate_workflow_text(
            """
version: 0
workflow: open-task
guards: []
steps:
  - name: remember-branch
    state_set:
      states.task_state[inputs.issue_ref].branch: ${inputs.branch}
  - name: forget-branch
    state_delete: states.task_state[inputs.issue_ref].branch
"""
        )

        self.assertEqual(report.status.value, "ok")
        self.assertEqual(report.diagnostics, ())

    def test_workflow_validation_rejects_mixed_step_forms(self) -> None:
        report = validate_workflow_text(
            """
version: 0
workflow: open-task
guards: []
steps:
  - name: remember-branch
    uses: shell.command
    state_delete: states.task_state[inputs.issue_ref].branch
    with:
      command: echo hi
"""
        )

        self.assertEqual(report.status.value, "validation_error")
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.form")

    def test_workflow_validation_rejects_with_without_uses(self) -> None:
        report = validate_workflow_text(
            """
version: 0
workflow: open-task
guards: []
steps:
  - name: remember-branch
    state_set:
      states.task_state[inputs.issue_ref].branch: ${inputs.branch}
    with:
      command: echo hi
"""
        )

        self.assertEqual(report.status.value, "validation_error")
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.with_without_uses")


if __name__ == "__main__":
    unittest.main()
