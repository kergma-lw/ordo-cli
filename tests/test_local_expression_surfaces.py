import unittest

from ordo.runtime.local_expression_contexts import LocalExpressionContext
from ordo.runtime.local_expressions import (
    parse_condition_local_expression,
    parse_embedded_value_local_expression,
    parse_local_expression,
    validate_parsed_local_expression,
)


class LocalExpressionSurfacesTest(unittest.TestCase):
    def test_guard_surface_parses_as_condition_context(self) -> None:
        parsed = parse_local_expression(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state != "CLOSED"',
            context=LocalExpressionContext.GUARD,
        )

        self.assertEqual(parsed.context, LocalExpressionContext.GUARD)
        self.assertIsNotNone(parsed.guard)
        self.assertEqual(validate_parsed_local_expression(parsed), ())

    def test_step_condition_surface_parses_as_condition_context(self) -> None:
        parsed = parse_condition_local_expression(
            'step.issue.outputs.open and inputs.enabled',
            context=LocalExpressionContext.STEP_CONDITION,
        )

        self.assertEqual(parsed.context, LocalExpressionContext.STEP_CONDITION)
        self.assertIsNotNone(parsed.value)

    def test_step_condition_surface_accepts_read_only_call_shapes(self) -> None:
        parsed = parse_condition_local_expression(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).exists',
            context=LocalExpressionContext.STEP_CONDITION,
        )

        self.assertEqual(validate_parsed_local_expression(parsed), ())

    def test_embedded_value_surface_parses_in_embedded_value_context(self) -> None:
        parsed = parse_embedded_value_local_expression('${inputs.title | trim | slug}')

        assert parsed is not None
        self.assertEqual(parsed.context, LocalExpressionContext.EMBEDDED_VALUE)
        self.assertIsNotNone(parsed.value)

    def test_embedded_value_surface_accepts_read_only_call_shapes(self) -> None:
        parsed = parse_embedded_value_local_expression('${gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body}')

        assert parsed is not None
        self.assertEqual(validate_parsed_local_expression(parsed), ())

    def test_include_binding_surface_parses_in_include_binding_context(self) -> None:
        parsed = parse_local_expression('step.issue.outputs.id', context=LocalExpressionContext.INCLUDE_BINDING)

        self.assertEqual(parsed.context, LocalExpressionContext.INCLUDE_BINDING)
        self.assertIsNotNone(parsed.value)

    def test_embedded_value_surface_rejects_non_dotted_call_target(self) -> None:
        parsed = parse_local_expression('inputs(repository=inputs.repository)', context=LocalExpressionContext.EMBEDDED_VALUE)

        self.assertEqual(
            {issue.code for issue in validate_parsed_local_expression(parsed)},
            {"validation.workflow.value_expr.inputs_call"},
        )

    def test_embedded_value_surface_rejects_duplicate_probe_argument_names(self) -> None:
        parsed = parse_local_expression(
            'gh.issue(repository=inputs.repository, repository=inputs.other_repository)',
            context=LocalExpressionContext.EMBEDDED_VALUE,
        )

        self.assertEqual(
            {issue.code for issue in validate_parsed_local_expression(parsed)},
            {"validation.workflow.value_expr.duplicate_argument"},
        )

    def test_embedded_value_surface_accepts_presence_check_on_lookup_reference(self) -> None:
        parsed = parse_local_expression('is_missing(inputs.priority)', context=LocalExpressionContext.EMBEDDED_VALUE)

        self.assertEqual(validate_parsed_local_expression(parsed), ())

    def test_embedded_value_surface_rejects_presence_check_on_computed_expression(self) -> None:
        parsed = parse_local_expression('is_missing(format("{}", inputs.priority))', context=LocalExpressionContext.EMBEDDED_VALUE)

        self.assertEqual(
            {issue.code for issue in validate_parsed_local_expression(parsed)},
            {"validation.workflow.value_expr.presence_check_argument"},
        )


if __name__ == "__main__":
    unittest.main()
