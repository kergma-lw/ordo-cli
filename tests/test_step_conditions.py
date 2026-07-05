import unittest

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import execute_workflow, explain_execution_result, load_workflow_text, validate_workflow_text

from tests.support import STANDARD_CONNECTOR_PROVIDER


class StepConditionsIntegrationTest(unittest.TestCase):
    def test_validate_and_execute_condition_with_eq_filter(self) -> None:
        workflow_text = """
version: 0
workflow: open-task
inputs:
  status: ok
blocks:
  - guards: []
  - steps:
      - name: comment
        if: ${inputs.status | eq("ok")}
        uses: shell.command
        with:
          command: printf executed
"""

        validation = validate_workflow_text(workflow_text)
        workflow = load_workflow_text(workflow_text)
        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(validation.status, RuntimeStatus.OK)
        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])
        self.assertEqual(result.outputs["step_condition_details"][0]["outcome"], "executed")
        self.assertIs(result.outputs["step_condition_details"][0]["result"], True)

    def test_execute_condition_false_preserves_skip_reason(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  status: closed
blocks:
  - guards: []
  - steps:
      - name: comment
        if: ${inputs.status | eq("ok")}
        uses: shell.command
        with:
          command: printf executed
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["comment"])
        self.assertEqual(result.outputs["step_condition_details"][0]["reason"], "condition_false")
        self.assertIs(result.outputs["step_condition_details"][0]["result"], False)

    def test_execute_composed_step_condition(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: true
  status: ok
blocks:
  - guards: []
  - steps:
      - name: comment
        if: ${inputs.enabled and (inputs.status | eq("ok"))}
        uses: shell.command
        with:
          command: printf executed
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])

    def test_execute_composed_step_condition_short_circuits_or(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: true
blocks:
  - guards: []
  - steps:
      - name: comment
        if: ${inputs.enabled or inputs.missing}
        uses: shell.command
        with:
          command: printf executed
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])

    def test_explain_execution_result_preserves_condition_evaluation_failure(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
blocks:
  - guards: []
  - steps:
      - name: comment
        if: ${inputs.enabled | not}
        uses: shell.command
        with:
          command: printf executed
"""
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["explanation"]["category"], "execution")
        self.assertEqual(result.outputs["step_condition_details"][0]["reason"], "condition_evaluation_failed")
        self.assertEqual(result.outputs["step_condition_details"][0]["error_code"], "runtime.value.input_missing")


if __name__ == "__main__":
    unittest.main()
