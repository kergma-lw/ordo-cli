import unittest

from ordo.runtime.local_expression_engine.core import (
    AdapterBindingNode,
    AdapterInvocationNode,
    BuiltinCallNode,
    FilterApplicationNode,
    LiteralNode,
    LocalExpressionParseError,
    ParsedLocalExpressionTree,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode,
)


class LocalExpressionEngineModelTest(unittest.TestCase):
    def test_model_can_represent_filtered_input_reference(self) -> None:
        reference = ReferenceNode(start=0, end=12, parts=("inputs", "title"))
        slug = FilterApplicationNode(start=15, end=19, name="slug")
        parsed = ParsedLocalExpressionTree(
            source="inputs.title | slug",
            root=PipelineNode(start=0, end=19, source=reference, filters=(slug,)),
        )

        self.assertEqual(parsed.root.source.parts, ("inputs", "title"))
        self.assertEqual(parsed.root.filters[0].name, "slug")

    def test_model_can_represent_state_read(self) -> None:
        parsed = ParsedLocalExpressionTree(
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
        parsed = ParsedLocalExpressionTree(
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
        error = LocalExpressionParseError("Expected expression term", 5, 6)

        diagnostic = error.to_diagnostic(path=("steps", "0", "with", "branch"), source="workflow.yaml", expression="foo |")

        self.assertEqual(diagnostic.code, "validation.workflow.value_expr.syntax")
        self.assertEqual(diagnostic.details["position"], 5)
        self.assertEqual(diagnostic.details["end"], 6)

    def test_model_can_represent_adapter_invocation_with_outer_bindings(self) -> None:
        parsed = ParsedLocalExpressionTree(
            source='markdown["section"].list->append_item(item) with{section: inputs.section}',
            root=AdapterInvocationNode(
                start=0,
                end=72,
                family="markdown",
                body='["section"].list->append_item(item)',
                bindings=(
                    AdapterBindingNode(
                        start=48,
                        end=71,
                        name="section",
                        value=ReferenceNode(start=57, end=71, parts=("inputs", "section")),
                    ),
                ),
            ),
        )

        self.assertEqual(parsed.root.family, "markdown")
        self.assertEqual(parsed.root.body, '["section"].list->append_item(item)')
        self.assertEqual(parsed.root.bindings[0].name, "section")
        self.assertEqual(parsed.root.bindings[0].value.parts, ("inputs", "section"))


if __name__ == "__main__":
    unittest.main()
