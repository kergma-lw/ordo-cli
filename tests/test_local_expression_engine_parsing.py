import unittest

from ordo.runtime.local_expression_engine.core import (
    AdapterBindingNode,
    AdapterInvocationNode,
    BinaryNode,
    BuiltinCallNode,
    CallArgumentNode,
    ConditionExpressionParseError,
    CallNode,
    FilterApplicationNode,
    ListNode,
    LocalExpressionParseError,
    LiteralNode,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode,
    StepReferenceNode,
    UnaryNode,
    parse_condition_expression,
    parse_local_expression_tree,
)


class LocalExpressionEngineParsingTest(unittest.TestCase):
    def test_parse_direct_reference(self) -> None:
        parsed = parse_local_expression_tree("inputs.title")

        self.assertIsInstance(parsed.root, ReferenceNode)
        self.assertEqual(parsed.root.parts, ("inputs", "title"))

    def test_parse_state_reference(self) -> None:
        parsed = parse_local_expression_tree("state.task_memory[inputs.issue_ref].branch")

        self.assertIsInstance(parsed.root, StateReferenceNode)
        self.assertEqual(parsed.root.state_role, "task_memory")
        self.assertEqual(parsed.root.key_reference, ("inputs", "issue_ref"))
        self.assertEqual(parsed.root.fields, ("branch",))

    def test_parse_pipe_chain(self) -> None:
        parsed = parse_local_expression_tree("inputs.title | trim | slug")

        self.assertIsInstance(parsed.root, PipelineNode)
        self.assertEqual(parsed.root.source.parts, ("inputs", "title"))
        self.assertEqual(parsed.root.filters, (
            FilterApplicationNode(start=15, end=19, name="trim"),
            FilterApplicationNode(start=22, end=26, name="slug"),
        ))

    def test_parse_filter_with_argument(self) -> None:
        parsed = parse_local_expression_tree('inputs.status | eq("ok")')

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
        parsed = parse_local_expression_tree("true")

        self.assertEqual(parsed.root, LiteralNode(start=0, end=4, value=True))

    def test_parse_rejects_missing_filter_name(self) -> None:
        with self.assertRaises(LocalExpressionParseError) as ctx:
            parse_local_expression_tree("inputs.title |")

        self.assertEqual(ctx.exception.message, "Expected filter name after '|'")

    def test_parse_rejects_non_input_state_key_reference(self) -> None:
        with self.assertRaises(LocalExpressionParseError) as ctx:
            parse_local_expression_tree("state.task_memory[foo.bar]")

        self.assertIn("State path key reference", ctx.exception.message)

    def test_parse_inline_format_call(self) -> None:
        parsed = parse_local_expression_tree('format("{}/{}", inputs.owner, inputs.repo | lower)')

        self.assertIsInstance(parsed.root, BuiltinCallNode)
        self.assertEqual(parsed.root.name, "format")
        self.assertEqual(parsed.root.arguments[0], LiteralNode(start=7, end=14, value="{}/{}"))
        self.assertEqual(parsed.root.arguments[1].parts, ("inputs", "owner"))
        self.assertIsInstance(parsed.root.arguments[2], PipelineNode)

    def test_parse_rejects_unterminated_string_literal(self) -> None:
        with self.assertRaises(LocalExpressionParseError) as ctx:
            parse_local_expression_tree('format("unterminated)')

        self.assertEqual(ctx.exception.message, "Unterminated string literal")

    def test_parse_boolean_composition_for_step_condition(self) -> None:
        parsed = parse_local_expression_tree(
            'inputs.enabled and (inputs.status | eq("ok"))',
            allow_boolean_composition=True,
        )

        self.assertIsInstance(parsed.root, BinaryNode)
        self.assertEqual(parsed.root.operator, "and")
        self.assertIsInstance(parsed.root.left, ReferenceNode)
        self.assertEqual(parsed.root.left.parts, ("inputs", "enabled"))
        self.assertIsInstance(parsed.root.right, PipelineNode)

    def test_parse_not_boolean_composition_for_step_condition(self) -> None:
        parsed = parse_local_expression_tree("not inputs.enabled", allow_boolean_composition=True)

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
        with self.assertRaises(LocalExpressionParseError) as ctx:
            parse_local_expression_tree("inputs.enabled and inputs.ready")

        self.assertEqual(ctx.exception.message, "Unexpected trailing token")

    def test_parse_list_literal(self) -> None:
        parsed = parse_local_expression_tree('["OPEN", "CLOSED"]')

        self.assertEqual(
            parsed.root,
            ListNode(
                start=0,
                end=18,
                items=(
                    LiteralNode(start=1, end=7, value="OPEN"),
                    LiteralNode(start=9, end=17, value="CLOSED"),
                ),
            ),
        )

    def test_parse_comparison_expression_when_boolean_mode_enabled(self) -> None:
        parsed = parse_local_expression_tree('inputs.status == "ok"', allow_boolean_composition=True)

        self.assertIsInstance(parsed.root, BinaryNode)
        self.assertEqual(parsed.root.operator, "==")

    def test_parse_probe_call_with_named_arguments_and_field_access(self) -> None:
        parsed = parse_local_expression_tree(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state'
        )

        self.assertEqual(
            parsed.root,
            CallNode(
                start=0,
                end=78,
                target=ReferenceNode(start=0, end=8, parts=("gh", "issue")),
                arguments=(
                    CallArgumentNode(
                        start=9,
                        end=37,
                        name="repository",
                        value=ReferenceNode(start=20, end=37, parts=("inputs", "repository")),
                    ),
                    CallArgumentNode(
                        start=39,
                        end=71,
                        name="issue_number",
                        value=ReferenceNode(start=52, end=71, parts=("inputs", "issue_number")),
                    ),
                ),
                fields=("state",),
            ),
        )

    def test_parse_negative_and_float_numbers(self) -> None:
        parsed = parse_local_expression_tree("-1.5")

        self.assertEqual(parsed.root, LiteralNode(start=0, end=4, value=-1.5))

    def test_parse_condition_surface_probe_composition(self) -> None:
        parsed = parse_condition_expression(
            'git.worktree.clean and gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state != "CLOSED"'
        )

        self.assertIsInstance(parsed.root, BinaryNode)
        self.assertEqual(parsed.root.operator, "and")
        self.assertIsInstance(parsed.root.left, ReferenceNode)
        self.assertEqual(parsed.root.left.parts, ("git", "worktree", "clean"))
        self.assertIsInstance(parsed.root.right, BinaryNode)
        self.assertEqual(parsed.root.right.operator, "!=")
        self.assertIsInstance(parsed.root.right.left, CallNode)
        self.assertEqual(parsed.root.right.left.target.parts, ("gh", "issue"))
        self.assertEqual(parsed.root.right.left.arguments[0].name, "repository")
        self.assertEqual(parsed.root.right.left.fields, ("state",))

    def test_parse_condition_surface_not_in_operator(self) -> None:
        parsed = parse_condition_expression('gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state not in ["CLOSED"]')

        self.assertIsInstance(parsed.root, BinaryNode)
        self.assertEqual(parsed.root.operator, "not in")

    def test_parse_condition_surface_rejects_positional_arguments(self) -> None:
        with self.assertRaises(ConditionExpressionParseError) as context:
            parse_condition_expression("gh.issue(inputs.issue).status")

        self.assertIn("Expected '=' after argument name", context.exception.message)

    def test_parse_condition_surface_nested_project_issue_probe(self) -> None:
        parsed = parse_condition_expression("gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id).exists")

        self.assertIsInstance(parsed.root, CallNode)
        self.assertEqual(parsed.root.target.parts, ("gh", "project", "issue"))
        self.assertEqual(parsed.root.arguments[0].name, "repository")
        self.assertEqual(parsed.root.arguments[1].name, "issue_number")
        self.assertEqual(parsed.root.fields, ("exists",))

    def test_parse_condition_surface_rejects_unterminated_string(self) -> None:
        with self.assertRaises(ConditionExpressionParseError) as context:
            parse_condition_expression('git.branch == "main')

        self.assertIn("Unterminated string literal", context.exception.message)

    def test_parse_adapter_invocation_with_outer_bindings(self) -> None:
        parsed = parse_local_expression_tree(
            'markdown["section"].list->add(item) with{section: inputs.section, item: step.prepare.outputs.text}'
        )

        self.assertEqual(
            parsed.root,
            AdapterInvocationNode(
                start=0,
                end=98,
                family="markdown",
                body='["section"].list->add(item)',
                bindings=(
                    AdapterBindingNode(
                        start=41,
                        end=64,
                        name="section",
                        value=ReferenceNode(start=50, end=64, parts=("inputs", "section")),
                    ),
                    AdapterBindingNode(
                        start=66,
                        end=97,
                        name="item",
                        value=StepReferenceNode(start=72, end=97, register="prepare", fields=("outputs", "text")),
                    ),
                ),
            ),
        )

    def test_parse_adapter_invocation_without_bindings(self) -> None:
        parsed = parse_local_expression_tree('markdown["Tasks"].list->add("Release build")')

        self.assertEqual(
            parsed.root,
            AdapterInvocationNode(
                start=0,
                end=44,
                family="markdown",
                body='["Tasks"].list->add("Release build")',
                bindings=(),
            ),
        )

    def test_parse_rejects_unclosed_outer_adapter_bindings(self) -> None:
        with self.assertRaises(LocalExpressionParseError) as context:
            parse_local_expression_tree('markdown["Tasks"] with{section: inputs.section')

        self.assertIn("close outer adapter binding suffix", context.exception.message)


if __name__ == "__main__":
    unittest.main()
