import unittest

from ordo.runtime.local_expression_engine.core import (
    BuiltinCallNode,
    EmbeddedValueExpressionParseError,
    FilterApplicationNode,
    LiteralNode,
    ParsedEmbeddedValueExpression,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode,
)


class LocalExpressionEngineModelTest(unittest.TestCase):
    def test_model_can_represent_filtered_input_reference(self) -> None:
        reference = ReferenceNode(start=0, end=12, parts=("inputs", "title"))
        slug = FilterApplicationNode(start=15, end=19, name="slug")
        parsed = ParsedEmbeddedValueExpression(
            source="inputs.title | slug",
            root=PipelineNode(start=0, end=19, source=reference, filters=(slug,)),
        )

        self.assertEqual(parsed.root.source.parts, ("inputs", "title"))
        self.assertEqual(parsed.root.filters[0].name, "slug")

    def test_model_can_represent_state_read(self) -> None:
        parsed = ParsedEmbeddedValueExpression(
            source="state.task_memory[inputs.issue_ref].branch",
            root=StateReferenceNode(
                start=0,
                end=40,
                state_role="task_memory",
                key_reference=("inputs", "issue_ref"),
                fields=("branch",),
            ),
        )

        self.assertEqual(parsed.root.state_role, "task_memory")
        self.assertEqual(parsed.root.key_reference, ("inputs", "issue_ref"))
        self.assertEqual(parsed.root.fields, ("branch",))

    def test_model_can_represent_root_builtin_call(self) -> None:
        owner = ReferenceNode(start=14, end=26, parts=("inputs", "owner"))
        repo = ReferenceNode(start=28, end=39, parts=("inputs", "repo"))
        parsed = ParsedEmbeddedValueExpression(
            source='format("{}/{}", inputs.owner, inputs.repo)',
            root=BuiltinCallNode(
                start=0,
                end=41,
                name="format",
                arguments=(LiteralNode(start=7, end=15, value="{}/{}"), owner, repo),
            ),
        )

        self.assertEqual(parsed.root.name, "format")
        self.assertEqual(parsed.root.arguments[0].value, "{}/{}")
        self.assertEqual(parsed.root.arguments[1].parts, ("inputs", "owner"))
        self.assertEqual(parsed.root.arguments[2].parts, ("inputs", "repo"))

    def test_parse_error_maps_to_structured_diagnostic(self) -> None:
        error = EmbeddedValueExpressionParseError("Expected expression term", 5, 6)

        diagnostic = error.to_diagnostic(path=("steps", "0", "with", "branch"), source="workflow.yaml", expression="foo |")

        self.assertEqual(diagnostic.code, "validation.workflow.value_expr.syntax")
        self.assertEqual(diagnostic.details["position"], 5)
        self.assertEqual(diagnostic.details["end"], 6)


if __name__ == "__main__":
    unittest.main()
