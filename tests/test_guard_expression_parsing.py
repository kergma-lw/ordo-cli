import unittest

from ordo.runtime.guard_expressions import BinaryNode, CallNode, GuardExpressionParseError, ReferenceNode, parse_guard_expression


class LegacyGuardExpressionParsingTest(unittest.TestCase):
    def test_parses_boolean_composition_and_probe_calls(self) -> None:
        parsed = parse_guard_expression(
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

    def test_parses_not_in_operator(self) -> None:
        parsed = parse_guard_expression('gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state not in ["CLOSED"]')

        self.assertIsInstance(parsed.root, BinaryNode)
        self.assertEqual(parsed.root.operator, "not in")

    def test_rejects_positional_arguments_in_current_grammar(self) -> None:
        with self.assertRaises(GuardExpressionParseError) as context:
            parse_guard_expression("gh.issue(inputs.issue).status")

        self.assertIn("Expected '=' after argument name", context.exception.message)

    def test_parses_nested_project_issue_probe(self) -> None:
        parsed = parse_guard_expression("gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id).exists")

        self.assertIsInstance(parsed.root, CallNode)
        self.assertEqual(parsed.root.target.parts, ("gh", "project", "issue"))
        self.assertEqual(parsed.root.arguments[0].name, "repository")
        self.assertEqual(parsed.root.arguments[1].name, "issue_number")
        self.assertEqual(parsed.root.fields, ("exists",))

    def test_rejects_unterminated_string(self) -> None:
        with self.assertRaises(GuardExpressionParseError) as context:
            parse_guard_expression('git.branch == "main')

        self.assertIn("Unterminated string literal", context.exception.message)
