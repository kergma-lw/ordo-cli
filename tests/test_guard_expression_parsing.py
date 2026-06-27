import unittest

from ordo.runtime.guard_expressions import BinaryNode, CallNode, GuardExpressionParseError, ReferenceNode, UnaryNode, parse_guard_expression


class GuardExpressionParsingTest(unittest.TestCase):
    def test_parses_boolean_composition_and_probe_calls(self) -> None:
        parsed = parse_guard_expression(
            'git.worktree.clean and not gh.issue(issue=inputs.issue).status in ["Done", "In review"]'
        )

        self.assertIsInstance(parsed.root, BinaryNode)
        self.assertEqual(parsed.root.operator, "and")
        self.assertIsInstance(parsed.root.left, ReferenceNode)
        self.assertEqual(parsed.root.left.parts, ("git", "worktree", "clean"))
        self.assertIsInstance(parsed.root.right, UnaryNode)
        inner = parsed.root.right.operand
        self.assertIsInstance(inner, BinaryNode)
        self.assertEqual(inner.operator, "in")
        self.assertIsInstance(inner.left, CallNode)
        self.assertEqual(inner.left.target.parts, ("gh", "issue"))
        self.assertEqual(inner.left.arguments[0].name, "issue")
        self.assertEqual(inner.left.fields, ("status",))

    def test_parses_not_in_operator(self) -> None:
        parsed = parse_guard_expression('gh.issue(issue=inputs.issue).status not in ["Done"]')

        self.assertIsInstance(parsed.root, BinaryNode)
        self.assertEqual(parsed.root.operator, "not in")

    def test_rejects_positional_arguments_in_current_grammar(self) -> None:
        with self.assertRaises(GuardExpressionParseError) as context:
            parse_guard_expression("gh.issue(inputs.issue).status")

        self.assertIn("Expected '=' after argument name", context.exception.message)

    def test_rejects_unterminated_string(self) -> None:
        with self.assertRaises(GuardExpressionParseError) as context:
            parse_guard_expression('git.branch == "main')

        self.assertIn("Unterminated string literal", context.exception.message)
