import unittest

from ordo.runtime.value_expressions import (
    BinaryNode,
    BuiltinCallNode,
    FilterApplicationNode,
    LiteralNode,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode,
    UnaryNode,
    ValueExpressionParseError,
    parse_value_expression,
)


class ValueExpressionParsingTest(unittest.TestCase):
    def test_parse_direct_reference(self) -> None:
        parsed = parse_value_expression("inputs.title")

        self.assertIsInstance(parsed.root, ReferenceNode)
        self.assertEqual(parsed.root.parts, ("inputs", "title"))

    def test_parse_state_reference(self) -> None:
        parsed = parse_value_expression("state.task_memory[inputs.issue_ref].branch")

        self.assertIsInstance(parsed.root, StateReferenceNode)
        self.assertEqual(parsed.root.state_role, "task_memory")
        self.assertEqual(parsed.root.key_reference, ("inputs", "issue_ref"))
        self.assertEqual(parsed.root.fields, ("branch",))

    def test_parse_pipe_chain(self) -> None:
        parsed = parse_value_expression("inputs.title | trim | slug")

        self.assertIsInstance(parsed.root, PipelineNode)
        self.assertEqual(parsed.root.source.parts, ("inputs", "title"))
        self.assertEqual(parsed.root.filters, (
            FilterApplicationNode(start=15, end=19, name="trim"),
            FilterApplicationNode(start=22, end=26, name="slug"),
        ))

    def test_parse_filter_with_argument(self) -> None:
        parsed = parse_value_expression('inputs.status | eq("ok")')

        self.assertIsInstance(parsed.root, PipelineNode)
        self.assertEqual(parsed.root.filters, (
            FilterApplicationNode(
                start=16,
                end=24,
                name="eq",
                arguments=(LiteralNode(start=19, end=23, value="ok"),),
            ),
        ))

    def test_parse_boolean_literal(self) -> None:
        parsed = parse_value_expression("true")

        self.assertEqual(parsed.root, LiteralNode(start=0, end=4, value=True))

    def test_parse_rejects_missing_filter_name(self) -> None:
        with self.assertRaises(ValueExpressionParseError) as ctx:
            parse_value_expression("inputs.title |")

        self.assertEqual(ctx.exception.message, "Expected filter name after '|'")

    def test_parse_rejects_non_input_state_key_reference(self) -> None:
        with self.assertRaises(ValueExpressionParseError) as ctx:
            parse_value_expression("state.task_memory[foo.bar]")

        self.assertIn("State path key reference", ctx.exception.message)

    def test_parse_inline_format_call(self) -> None:
        parsed = parse_value_expression('format("{}/{}", inputs.owner, inputs.repo | lower)')

        self.assertIsInstance(parsed.root, BuiltinCallNode)
        self.assertEqual(parsed.root.name, "format")
        self.assertEqual(parsed.root.arguments[0], LiteralNode(start=7, end=14, value="{}/{}"))
        self.assertEqual(parsed.root.arguments[1].parts, ("inputs", "owner"))
        self.assertIsInstance(parsed.root.arguments[2], PipelineNode)

    def test_parse_rejects_unterminated_string_literal(self) -> None:
        with self.assertRaises(ValueExpressionParseError) as ctx:
            parse_value_expression('format("unterminated)')

        self.assertEqual(ctx.exception.message, "Unterminated string literal")

    def test_parse_boolean_composition_for_step_condition(self) -> None:
        parsed = parse_value_expression(
            'inputs.enabled and (inputs.status | eq("ok"))',
            allow_boolean_composition=True,
        )

        self.assertIsInstance(parsed.root, BinaryNode)
        self.assertEqual(parsed.root.operator, "and")
        self.assertIsInstance(parsed.root.left, ReferenceNode)
        self.assertEqual(parsed.root.left.parts, ("inputs", "enabled"))
        self.assertIsInstance(parsed.root.right, PipelineNode)

    def test_parse_not_boolean_composition_for_step_condition(self) -> None:
        parsed = parse_value_expression("not inputs.enabled", allow_boolean_composition=True)

        self.assertEqual(
            parsed.root,
            UnaryNode(
                start=0,
                end=18,
                operator="not",
                operand=ReferenceNode(start=4, end=18, parts=("inputs", "enabled")),
            ),
        )

    def test_parse_rejects_boolean_composition_when_not_enabled(self) -> None:
        with self.assertRaises(ValueExpressionParseError) as ctx:
            parse_value_expression("inputs.enabled and inputs.ready")

        self.assertEqual(ctx.exception.message, "Unexpected trailing token")


if __name__ == "__main__":
    unittest.main()
