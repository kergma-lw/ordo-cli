import json
import tempfile
import unittest

from ordo.model.workflow import Workflow
from ordo.runtime import load_workflow_text
from ordo.runtime.value_expressions import ValueExpressionEvaluationError, evaluate_value_expression, parse_value_expression


class ValueExpressionEvaluationTest(unittest.TestCase):
    def test_evaluate_input_reference_filter_chain(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  title: "  Hello World  "
guards: []
steps: []
"""
        )

        parsed = parse_value_expression("inputs.title | trim | lower | slug")

        value = evaluate_value_expression(parsed, workflow)

        self.assertEqual(value, "hello-world")

    def test_evaluate_state_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "values": {"owner/repo#1": {"branch": "task/1-demo"}}}, handle)

            workflow = load_workflow_text(
                f"""
version: 0
workflow: demo
inputs:
  issue_ref: owner/repo#1
state_needs:
  task_memory: {{}}
guards: []
steps: []
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

            parsed = parse_value_expression("state.task_memory[inputs.issue_ref].branch")

            value = evaluate_value_expression(parsed, workflow)

            self.assertEqual(value, "task/1-demo")

    def test_evaluate_reports_unknown_filter(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  title: hello
guards: []
steps: []
"""
        )

        parsed = parse_value_expression("inputs.title | missing")

        with self.assertRaises(ValueExpressionEvaluationError) as ctx:
            evaluate_value_expression(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_unknown")

    def test_evaluate_reports_filter_type_error(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  number: 7
guards: []
steps: []
"""
        )

        parsed = parse_value_expression("inputs.number | lower")

        with self.assertRaises(ValueExpressionEvaluationError) as ctx:
            evaluate_value_expression(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_type_invalid")

    def test_evaluate_inline_format_call(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  type: Task
  issue_number: 7
  title: "Hello World"
guards: []
steps: []
"""
        )

        parsed = parse_value_expression('format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug)')

        value = evaluate_value_expression(parsed, workflow)

        self.assertEqual(value, "task/7-hello-world")

    def test_evaluate_inline_format_rejects_wrong_arg_count(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  owner: acme
guards: []
steps: []
"""
        )

        parsed = parse_value_expression('format("{}/{}", inputs.owner)')

        with self.assertRaises(ValueExpressionEvaluationError) as ctx:
            evaluate_value_expression(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.format_args_invalid")

    def test_evaluate_inline_format_rejects_non_string_template(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs: {}
guards: []
steps: []
"""
        )

        parsed = parse_value_expression("format(7)")

        with self.assertRaises(ValueExpressionEvaluationError) as ctx:
            evaluate_value_expression(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.format_template_invalid")

    def test_evaluate_eq_filter_returns_boolean(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  status: ok
guards: []
steps: []
"""
        )

        parsed = parse_value_expression('inputs.status | eq("ok")')

        self.assertIs(evaluate_value_expression(parsed, workflow), True)

    def test_evaluate_ne_filter_can_compare_boolean_literal(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  open: false
guards: []
steps: []
"""
        )

        parsed = parse_value_expression("inputs.open | ne(true)")

        self.assertIs(evaluate_value_expression(parsed, workflow), True)

    def test_evaluate_not_filter_negates_boolean(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  open: false
guards: []
steps: []
"""
        )

        parsed = parse_value_expression("inputs.open | not")

        self.assertIs(evaluate_value_expression(parsed, workflow), True)

    def test_evaluate_not_filter_rejects_non_boolean_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  status: ok
guards: []
steps: []
"""
        )

        parsed = parse_value_expression("inputs.status | not")

        with self.assertRaises(ValueExpressionEvaluationError) as ctx:
            evaluate_value_expression(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_type_invalid")


if __name__ == "__main__":
    unittest.main()
