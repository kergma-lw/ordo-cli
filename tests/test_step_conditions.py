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
        if: inputs.status | eq("ok")
        uses: shell.command
        with:
          command: "printf executed"
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
        if: inputs.status | eq("ok")
        uses: shell.command
        with:
          command: "printf executed"
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
        if: inputs.enabled and (inputs.status | eq("ok"))
        uses: shell.command
        with:
          command: "printf executed"
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])

    def test_execute_composed_step_condition_short_circuits_or(self) -> None:
        loaded = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: {}
  missing: {}
blocks:
  - guards: []
  - steps:
      - name: comment
        if: inputs.enabled or inputs.missing
        uses: shell.command
        with:
          command: "printf executed"
"""
        )
        workflow = loaded.__class__(
            version=loaded.version,
            workflow=loaded.workflow,
            inputs={"enabled": True},
            declared_inputs=loaded.declared_inputs,
            blocks=loaded.blocks,
            source_path=loaded.source_path,
            launch_dir=loaded.launch_dir,
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])

    def test_explain_execution_result_preserves_condition_evaluation_failure(self) -> None:
        loaded = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: {}
blocks:
  - guards: []
  - steps:
      - name: comment
        if: inputs.enabled | not
        uses: shell.command
        with:
          command: "printf executed"
"""
        )
        workflow = loaded.__class__(
            version=loaded.version,
            workflow=loaded.workflow,
            inputs={},
            declared_inputs=loaded.declared_inputs,
            blocks=loaded.blocks,
            source_path=loaded.source_path,
            launch_dir=loaded.launch_dir,
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["explanation"]["category"], "execution")
        self.assertEqual(result.outputs["step_condition_details"][0]["reason"], "condition_evaluation_failed")
        self.assertEqual(result.outputs["step_condition_details"][0]["error_code"], "runtime.value.input_missing")

    def test_execute_bare_step_condition(self) -> None:
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
        if: inputs.enabled
        uses: shell.command
        with:
          command: "printf executed"
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])

    def test_execute_step_condition_can_use_workflow_let_binding(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: true
let:
  should_comment: inputs.enabled
blocks:
  - guards: []
  - steps:
      - name: comment
        if: should_comment
        uses: shell.command
        with:
          command: "printf executed"
"""
        )

        validation = validate_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: true
let:
  should_comment: inputs.enabled
blocks:
  - guards: []
  - steps:
      - name: comment
        if: should_comment
        uses: shell.command
        with:
          command: "printf executed"
"""
        )
        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(validation.status, RuntimeStatus.OK)
        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])

    def test_execute_structured_list_step_condition(self) -> None:
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
        if:
          - inputs.enabled
          - inputs.status | eq("ok")
        uses: shell.command
        with:
          command: "printf executed"
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])

    def test_execute_structured_any_step_condition(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: false
  status: ok
blocks:
  - guards: []
  - steps:
      - name: comment
        if:
          any:
            - inputs.enabled
            - inputs.status | eq("ok")
        uses: shell.command
        with:
          command: "printf executed"
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])

    def test_execute_structured_not_step_condition(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: false
blocks:
  - guards: []
  - steps:
      - name: comment
        if:
          not: inputs.enabled
        uses: shell.command
        with:
          command: "printf executed"
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])

    def test_execute_gate_failure_lists_all_failed_conditions(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: gate-check
blocks:
  - guards: []
  - steps:
      - name: ready-a
        value: false
        register: ready_a
      - name: ready-b
        value: false
        register: ready_b
      - name: ready-c
        value: true
        register: ready_c
      - name: mutate
        uses: shell.command
        with:
          command: "printf executed"
        gate:
          all:
            - step.ready_a.outputs.value
            - step.ready_b.outputs.value
            - step.ready_c.outputs.value
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["executed_steps"], ["ready-a", "ready-b", "ready-c"])
        self.assertEqual(result.outputs["gate_blockers"], ["mutate"])
        gate_detail = result.outputs["step_gate_details"][0]
        failed = [item["expression"] for item in gate_detail["failed"]]
        self.assertEqual(failed, ["step.ready_a.outputs.value", "step.ready_b.outputs.value"])

    def test_execute_if_false_does_not_evaluate_gate(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: gate-check
inputs:
  enabled: false
blocks:
  - guards: []
  - steps:
      - name: mutate
        if: inputs.enabled
        uses: shell.command
        with:
          command: "printf executed"
        gate: inputs.enabled | not
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["skipped_steps"], ["mutate"])
        self.assertEqual(result.outputs["step_gate_details"], [])

    def test_run_gate_failure_diagnostic_uses_structural_any_semantics(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: gate-check
blocks:
  - guards: []
  - steps:
      - name: linked
        value:
          exists: true
          type: "Task"
          status: "Backlog"
        register: linked_project_issue
      - name: gate-linked-task
        gate:
          all:
            - step.linked_project_issue.outputs.value.exists
            - any:
                - step.linked_project_issue.outputs.value.type | eq("Task")
                - step.linked_project_issue.outputs.value.type | eq("Bug")
            - step.linked_project_issue.outputs.value.status | eq("Ready")
      - name: mutate
        result:
          summary: "done"
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        diagnostic = next(item for item in result.diagnostics if item.code == "runtime.step.gate.failed")
        self.assertEqual(diagnostic.details["failed_conditions"], ['step.linked_project_issue.outputs.value.status | eq("Ready")'])

    def test_explain_structured_condition_failure_preserves_error(self) -> None:
        loaded = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: true
  missing: {}
blocks:
  - guards: []
  - steps:
      - name: comment
        if:
          - inputs.enabled
          - inputs.missing
        uses: shell.command
        with:
          command: "printf executed"
"""
        )

        workflow = loaded.__class__(
            version=loaded.version,
            workflow=loaded.workflow,
            inputs={"enabled": True},
            declared_inputs=loaded.declared_inputs,
            blocks=loaded.blocks,
            source_path=loaded.source_path,
            launch_dir=loaded.launch_dir,
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["step_condition_details"][0]["reason"], "condition_evaluation_failed")
        self.assertEqual(result.outputs["step_condition_details"][0]["error_code"], "runtime.value.input_missing")

    def test_execute_guard_can_use_workflow_let_binding(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  enabled: true
let:
  can_run: inputs.enabled
blocks:
  - guards:
      - can_run
  - steps:
      - name: comment
        uses: shell.command
        with:
          command: "printf executed"
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["comment"])


if __name__ == "__main__":
    unittest.main()
