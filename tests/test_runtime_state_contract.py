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


if __name__ == "__main__":
    unittest.main()
