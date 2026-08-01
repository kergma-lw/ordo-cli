import json
import tempfile
import unittest

from ordo.model.diagnostic import Diagnostic
from ordo.model.workflow import Workflow
from ordo.runtime import load_workflow_text
from ordo.runtime.local_expression_engine.core import (
    ConditionObservationRequest,
    ConditionObservationResult,
    LocalExpressionEvaluationError,
    ReadOnlyObservationSession,
    evaluate_condition_expression,
    evaluate_local_expression_tree,
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

    def test_evaluate_is_string_filter_returns_true_for_string_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  title: ok
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.title | is_string")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_is_number_filter_rejects_boolean_values_as_numbers(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  open: true
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.open | is_number")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), False)

    def test_evaluate_is_integer_filter_rejects_float_literal_with_zero_fraction(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  count: 1.0
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.count | is_integer")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), False)

    def test_evaluate_is_boolean_filter_returns_true_for_boolean_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  open: true
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.open | is_boolean")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_in_filter_accepts_dynamic_list_container(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  status: ready
  allowed:
    - new
    - ready
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.status | in(inputs.allowed)")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_in_filter_rejects_non_list_container(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  status: ready
  allowed: ready
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.status | in(inputs.allowed)")

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_type_invalid")

    def test_evaluate_eq_filter_uses_strict_json_equality(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  one: 1
  truthy: true
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.one | eq(inputs.truthy)")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), False)

    def test_evaluate_in_filter_uses_strict_json_membership(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  value: 1
  allowed:
    - true
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("inputs.value | in(inputs.allowed)")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), False)

    def test_evaluate_field_filter_projects_object_value(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"payload": {"results": [{"value": 7}]}} ,
        )

        parsed = parse_local_expression_tree('inputs.payload | field("results[0].value")')

        self.assertEqual(evaluate_local_expression_tree(parsed, workflow), 7)

    def test_evaluate_field_filter_projects_array_values_with_null_for_missing_items(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "payload": [
                    {"results": [{"value": 7}]},
                    {"other": "nope"},
                    {"results": [{"value": 9}]},
                ]
            },
        )

        parsed = parse_local_expression_tree('inputs.payload | field("results[0].value")')

        self.assertEqual(evaluate_local_expression_tree(parsed, workflow), [7, None, 9])

    def test_evaluate_field_filter_rejects_missing_object_path(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"payload": {"other": "nope"}},
        )

        parsed = parse_local_expression_tree('inputs.payload | field("results[0]")')

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.field_path_missing")

    def test_evaluate_field_filter_rejects_non_collection_input(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"payload": "text"},
        )

        parsed = parse_local_expression_tree('inputs.payload | field("results")')

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_type_invalid")

    def test_evaluate_field_filter_rejects_invalid_path_syntax(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"payload": {"results": [{"value": 7}]}} ,
        )

        parsed = parse_local_expression_tree('inputs.payload | field("results[")')

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.field_path_invalid")

    def test_evaluate_flatten_filter_flattens_one_level(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"items": [[1, 2], [3], 4]},
        )

        parsed = parse_local_expression_tree("inputs.items | flatten")

        self.assertEqual(evaluate_local_expression_tree(parsed, workflow), [1, 2, 3, 4])

    def test_evaluate_flatten_filter_rejects_non_array_input(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"items": "text"},
        )

        parsed = parse_local_expression_tree("inputs.items | flatten")

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_type_invalid")

    def test_evaluate_first_filter_returns_null_for_empty_array(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"items": []},
        )

        parsed = parse_local_expression_tree("inputs.items | first")

        self.assertIsNone(evaluate_local_expression_tree(parsed, workflow))

    def test_evaluate_last_filter_returns_last_array_item(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"items": [1, 2, 3]},
        )

        parsed = parse_local_expression_tree("inputs.items | last")

        self.assertEqual(evaluate_local_expression_tree(parsed, workflow), 3)

    def test_evaluate_length_filter_counts_arrays_objects_and_strings(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"items": [1, 2, 3], "payload": {"a": 1, "b": 2}, "title": "hello"},
        )

        self.assertEqual(evaluate_local_expression_tree(parse_local_expression_tree("inputs.items | length"), workflow), 3)
        self.assertEqual(evaluate_local_expression_tree(parse_local_expression_tree("inputs.payload | length"), workflow), 2)
        self.assertEqual(evaluate_local_expression_tree(parse_local_expression_tree("inputs.title | length"), workflow), 5)

    def test_evaluate_length_filter_rejects_other_input_shapes(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"enabled": True},
        )

        parsed = parse_local_expression_tree("inputs.enabled | length")

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_type_invalid")

    def test_evaluate_unique_filter_preserves_first_occurrence_order(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"items": ["a", "b", "a", "c", "b"]},
        )

        parsed = parse_local_expression_tree("inputs.items | unique")

        self.assertEqual(evaluate_local_expression_tree(parsed, workflow), ["a", "b", "c"])

    def test_evaluate_unique_filter_ignores_object_key_order_but_preserves_array_order_significance(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "items": [
                    {"a": 1, "b": 2},
                    {"b": 2, "a": 1},
                    [1, 2],
                    [2, 1],
                ]
            },
        )

        parsed = parse_local_expression_tree("inputs.items | unique")

        self.assertEqual(evaluate_local_expression_tree(parsed, workflow), [{"a": 1, "b": 2}, [1, 2], [2, 1]])

    def test_evaluate_unique_filter_keeps_numeric_forms_distinct(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"items": [1, 1.0, 1, 1.0]},
        )

        parsed = parse_local_expression_tree("inputs.items | unique")

        self.assertEqual(evaluate_local_expression_tree(parsed, workflow), [1, 1.0])

    def test_evaluate_unique_filter_rejects_non_array_input(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"items": {"a": 1}},
        )

        parsed = parse_local_expression_tree("inputs.items | unique")

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.filter_type_invalid")

    def test_evaluate_is_missing_returns_true_for_missing_input(self) -> None:
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

        parsed = parse_local_expression_tree("is_missing(inputs.priority)")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_is_present_treats_explicit_null_as_present(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  priority: null
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree("is_present(inputs.priority)")

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_presence_check_rejects_computed_expression_argument(self) -> None:
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

        parsed = parse_local_expression_tree('is_missing(format("{}", inputs.title))')

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.presence_check_argument")

    def test_evaluate_is_present_accepts_adapter_invocation_when_path_exists(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  body: |
    ## Tasks

    - repo/name#1
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('is_present(markdown["Tasks"] with{root: inputs.body})')

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_is_present_accepts_list_item_adapter_path(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  body: |
    ## Tasks

    - repo/name#1
    - repo/name#2
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('is_present(markdown["Tasks"].list[1] with{root: inputs.body})')

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_is_present_accepts_text_adapter_invocation_when_match_exists(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  body: hello world
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('is_present(text.find("world") with{root: inputs.body})')

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_is_present_accepts_json_adapter_invocation_when_path_exists(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  body: '{"user":{"name":"Ada"}}'
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('is_present(json.user.name with{root: inputs.body})')

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_is_missing_accepts_adapter_invocation_when_path_absent(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  body: |
    ## Notes

    hello
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('is_missing(markdown["Tasks"] with{root: inputs.body})')

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_is_missing_accepts_text_adapter_invocation_when_match_absent(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  body: hello world
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('is_missing(text.find("planet") with{root: inputs.body})')

        self.assertIs(evaluate_local_expression_tree(parsed, workflow), True)

    def test_evaluate_presence_check_propagates_non_not_found_adapter_error(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  body: |
    ## Tasks

    First.

    Second.
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('is_present(markdown["Tasks"].paragraph with{root: inputs.body})')

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.adapter_ambiguous")

    def test_evaluate_presence_check_rejects_write_adapter_invocation(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  body: |
    ## Tasks

    - repo/name#1
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('is_present(markdown["Tasks"].list->add("repo/name#2") with{root: inputs.body})')

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.presence_check_argument")

    def test_evaluate_presence_check_propagates_text_collection_misuse(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  body: |
    hello
    world
blocks:
  - guards: []
  - steps: []
"""
        )

        parsed = parse_local_expression_tree('is_present(text.lines.after("h") with{root: inputs.body})')

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow)

        self.assertEqual(ctx.exception.code, "runtime.value.adapter_invalid_path")

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
        parsed = parse_local_expression_tree(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN"',
            allow_boolean_composition=True,
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
        parsed = parse_local_expression_tree(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN" and gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN"',
            allow_boolean_composition=True,
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

    def test_condition_evaluation_caches_failed_probe_diagnostics_once(self) -> None:
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
        parsed = parse_local_expression_tree(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN" and gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN"',
            allow_boolean_composition=True,
        )
        count = 0

        def observe(_: ConditionObservationRequest) -> ConditionObservationResult:
            nonlocal count
            count += 1
            return ConditionObservationResult(
                status="probe_failed",
                value=None,
                diagnostics=(Diagnostic(code="probe.failed", level="error", message="boom", path=()),),
                reference="gh.issue",
            )

        result = evaluate_condition_expression(parsed, workflow, observe=observe)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(count, 1)
        self.assertEqual(result.cache_entries, 1)
        self.assertEqual([item.code for item in result.diagnostics], ["probe.failed"])

    def test_observation_session_caches_successful_probe_once(self) -> None:
        observed: list[ConditionObservationRequest] = []

        session = ReadOnlyObservationSession(
            lambda request: observed.append(request)
            or ConditionObservationResult(status="ok", value="OPEN", reference="gh.issue")
        )

        request = ConditionObservationRequest(
            expression_text="gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state",
            target=("gh", "issue"),
            fields=("state",),
            arguments=(("repository", "owner/repo"), ("issue_number", 7)),
        )

        first = session.observe(request)
        second = session.observe(request)

        self.assertFalse(first.cached)
        self.assertTrue(second.cached)
        self.assertEqual(first.result.value, "OPEN")
        self.assertEqual(second.result.value, "OPEN")
        self.assertEqual(len(observed), 1)
        self.assertEqual(session.cache_entries, 1)

    def test_condition_evaluation_accepts_shared_observation_session(self) -> None:
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
        parsed = parse_local_expression_tree(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN" and gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN"',
            allow_boolean_composition=True,
        )
        count = 0

        def observe(_: ConditionObservationRequest) -> ConditionObservationResult:
            nonlocal count
            count += 1
            return ConditionObservationResult(status="ok", value="OPEN", reference="gh.issue")

        session = ReadOnlyObservationSession(observe)

        result = evaluate_condition_expression(parsed, workflow, session=session)

        self.assertEqual(result.status, "ok")
        self.assertIs(result.value, True)
        self.assertEqual(count, 1)
        self.assertEqual(result.cache_entries, 1)

    def test_observation_session_canonicalizes_cache_keys_for_equivalent_calls(self) -> None:
        observed: list[ConditionObservationRequest] = []
        session = ReadOnlyObservationSession(
            lambda request: observed.append(request)
            or ConditionObservationResult(status="ok", value="OPEN", reference="gh.issue")
        )

        first = ConditionObservationRequest(
            expression_text="gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state",
            target=("gh", "issue"),
            fields=("state",),
            arguments=(("repository", "owner/repo"), ("issue_number", 7)),
        )
        second = ConditionObservationRequest(
            expression_text="gh.issue( issue_number = inputs.issue_number , repository = inputs.repository ).state",
            target=("gh", "issue"),
            fields=("state",),
            arguments=(("issue_number", 7), ("repository", "owner/repo")),
        )

        first_result = session.observe(first)
        second_result = session.observe(second)

        self.assertFalse(first_result.cached)
        self.assertTrue(second_result.cached)
        self.assertEqual(len(observed), 1)
        self.assertEqual(session.cache_entries, 1)

    def test_value_evaluation_executes_read_only_call_with_shared_session(self) -> None:
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
        parsed = parse_local_expression_tree("gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body")
        observed: list[ConditionObservationRequest] = []
        session = ReadOnlyObservationSession(
            lambda request: observed.append(request)
            or ConditionObservationResult(status="ok", value="Issue body", reference="gh.issue")
        )

        value = evaluate_local_expression_tree(parsed, workflow, observation_session=session)

        self.assertEqual(value, "Issue body")
        self.assertEqual(observed[0].target, ("gh", "issue"))
        self.assertEqual(observed[0].fields, ("body",))
        self.assertEqual(observed[0].arguments, (("repository", "owner/repo"), ("issue_number", 7)))

    def test_value_evaluation_propagates_probe_failure(self) -> None:
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
        parsed = parse_local_expression_tree("gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body")
        session = ReadOnlyObservationSession(
            lambda _: ConditionObservationResult(
                status="probe_failed",
                value=None,
                diagnostics=(Diagnostic(code="probe.failed", level="error", message="boom", path=()),),
                reference="gh.issue",
            )
        )

        with self.assertRaises(LocalExpressionEvaluationError) as ctx:
            evaluate_local_expression_tree(parsed, workflow, observation_session=session)

        self.assertEqual(ctx.exception.code, "runtime.value.call_probe_failed")


if __name__ == "__main__":
    unittest.main()
