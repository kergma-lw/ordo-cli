import json
import tempfile
import unittest

from ordo.model.workflow import Workflow
from ordo.runtime import load_workflow_text
from ordo.runtime.local_expression_engine.core import (
    ConditionObservationRequest,
    ConditionObservationResult,
    LocalExpressionEvaluationError,
    evaluate_condition_expression,
    evaluate_local_expression_tree,
    parse_condition_expression,
    parse_local_expression_tree,
)


class LocalExpressionEngineEvaluationTest(unittest.TestCase):
    def test_evaluate_input_reference_filter_chain(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  title: "  Hello World  "
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.title | trim | lower | slug")

        value = evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(value, "hello-world")

    def test_evaluate_state_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump({"owner/repo#1": {"branch": "task/1-demo"}}, handle)

            workflow = load_workflow_text(
                f"""
version: 0
workflow: demo
inputs:
  issue_ref: owner/repo#1
state_needs:
  task_memory: {{}}
blocks:
  - guards: []
  - steps: []
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

            parsed = parse_local_expression_tree("state.task_memory[inputs.issue_ref].branch")

            value = evaluate_local_expression_tree(parsed, workflow)

            self.assertEqual(value, "task/1-demo")

    def test_evaluate_reports_unknown_filter(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  title: hello
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.title | missing")

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_unknown")

    def test_evaluate_reports_filter_type_error(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  number: 7
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.number | lower")

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

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
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug)')

        value = evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(value, "task/7-hello-world")

    def test_evaluate_inline_format_rejects_wrong_arg_count(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  owner: acme
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('format("{}/{}", inputs.owner)')

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.format_args_invalid")

    def test_evaluate_inline_format_rejects_non_string_template(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs: {}
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("format(7)")

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.format_template_invalid")

    def test_evaluate_eq_filter_returns_boolean(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  status: ok
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('inputs.status | eq("ok")')

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_ne_filter_can_compare_boolean_literal(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  open: false
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.open | ne(true)")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_not_filter_negates_boolean(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  open: false
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.open | not")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_not_filter_rejects_non_boolean_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  status: ok
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.status | not")

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_type_invalid")

    def test_evaluate_comparison_expression(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  status: ok
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('inputs.status == "ok"', allow_boolean_composition=True)

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_membership_expression(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  status: ok
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('inputs.status in ["ok", "closed"]', allow_boolean_composition=True)

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_condition_evaluation_uses_observer_inside_canonical_engine(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  repository: owner/repo
  issue_number: 7
blocks:
  - guards: []
  - steps: []
"""
        )
        parsed = parse_condition_expression(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN"'
        )
        observed: list[ConditionObservationRequest] = []

        result = evaluate_condition_expression(
            parsed,
            workflow,
            observe=lambda request: observed.append(request)
            or ConditionObservationResult(status="ok", value="OPEN", reference="gh.issue"),
        )

        self.assertEqual(result.status, "ok")
        self.assertIs(result.value, True)
        self.assertEqual(observed[0].target, ("gh", "issue"))
        self.assertEqual(observed[0].arguments, (("repository", "owner/repo"), ("issue_number", 7)))
        self.assertEqual(result.trace[-1].operator, "==")

    def test_condition_evaluation_caches_repeated_probe_observation(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  repository: owner/repo
  issue_number: 7
blocks:
  - guards: []
  - steps: []
"""
        )
        parsed = parse_condition_expression(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN" and gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN"'
        )
        count = 0

        def observe(_: ConditionObservationRequest) -> ConditionObservationResult:
            nonlocal count
            count += 1
            return ConditionObservationResult(status="ok", value="OPEN", reference="gh.issue")

        result = evaluate_condition_expression(parsed, workflow, observe=observe)

        self.assertEqual(result.status, "ok")
        self.assertIs(result.value, True)
        self.assertEqual(count, 1)
        self.assertEqual(result.cache_entries, 1)


if __name__ == "__main__":
    unittest.main()
