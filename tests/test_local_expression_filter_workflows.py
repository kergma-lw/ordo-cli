import unittest

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import execute_workflow, explain_execution_result, load_workflow_text, validate_workflow_text

from tests.support import STANDARD_CONNECTOR_PROVIDER


class LocalExpressionFilterWorkflowIntegrationTest(unittest.TestCase):
    def test_validate_and_execute_workflow_with_in_filter_and_boolean_value_flow(self) -> None:
        workflow_text = """
version: 0
workflow: local-expression-filters
inputs:
  title: Example Task
  status: ready
  allowed:
    - ready
    - blocked
blocks:
  - guards: []
  - steps:
      - name: compute-membership
        value: ${inputs.status | in(inputs.allowed)}
        register: allowed_status
      - name: announce
        if: ${step.allowed_status.outputs.value | is_boolean}
        uses: shell.command
        with:
          command: ${format("printf {}", inputs.title | slug)}
"""

        validation = validate_workflow_text(workflow_text)
        workflow = load_workflow_text(workflow_text)
        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(validation.status, RuntimeStatus.OK)
        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["compute-membership", "announce"])
        self.assertEqual(result.operation_results[0].outputs.get("value"), True)
        self.assertEqual(result.operation_results[1].outputs.get("stdout"), "example-task")

    def test_workflow_reports_in_filter_container_failure_from_authored_step_condition(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: local-expression-filters
inputs:
  status: ready
  allowed: ready
blocks:
  - guards: []
  - steps:
      - name: announce
        if: ${inputs.status | in(inputs.allowed)}
        uses: shell.command
        with:
          command: printf executed
"""
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["step_condition_details"][0]["reason"], "condition_evaluation_failed")
        self.assertEqual(result.outputs["step_condition_details"][0]["error_code"], "runtime.value.filter_type_invalid")


if __name__ == "__main__":
    unittest.main()
