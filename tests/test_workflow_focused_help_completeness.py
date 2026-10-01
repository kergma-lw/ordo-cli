"""Completeness checks for source-owned workflow focused help."""

import pytest

# Load the public help entrypoint first; it establishes the runtime/model import
# order used by the CLI before this contract-level audit reads the declarations.
from ordo import help_cli  # noqa: F401
from ordo.model.human import human_mapping
from ordo.model.workflow_contract import (
    WORKFLOW_ADDITIONAL_FOCUSED_DESCRIBE_HUMAN,
    WORKFLOW_FOCUSED_DESCRIBE_HUMAN,
)
from ordo.runtime.authoring_human import WORKFLOW_RULE_EXAMPLE_FOCUSED_DESCRIBE_HUMAN
from ordo.runtime.authoring_human import workflow_rules_focused_describe_human
from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS


def _text(handle: str) -> str:
    declaration = (
        WORKFLOW_FOCUSED_DESCRIBE_HUMAN | WORKFLOW_ADDITIONAL_FOCUSED_DESCRIBE_HUMAN
    )[handle]
    return str(human_mapping(declaration))


@pytest.mark.parametrize(
    ("category", "handles", "required_terms"),
    [
        (
            "filters",
            [f"workflow.local_expression.filter.{name}" for name in VALUE_EXPRESSION_FILTERS],
            ("What happens",),
        ),
        (
            "builtins",
            [f"workflow.local_expression.builtin.{name}" for name in VALUE_EXPRESSION_BUILTINS],
            ("What happens",),
        ),
        (
            "run fields",
            [f"workflow.run.{name}" for name in ("run", "with", "for_each", "steps", "if", "gate", "register")],
            ("What happens",),
        ),
        (
            "step fields",
            [f"workflow.step.{name}" for name in ("name", "uses", "with", "run", "for_each", "steps", "if", "gate", "result", "publish")],
            ("What happens",),
        ),
    ],
)
def test_workflow_leaf_guides_publish_authored_semantics(category, handles, required_terms):
    """Leaves teach their actual authored shape rather than only an identifier."""

    for handle in handles:
        text = _text(handle)
        assert "published filter identifier" not in text
        assert "published builtin identifier" not in text
        assert "published run-field identifier" not in text
        assert "published step-field identifier" not in text
        assert "Related surfaces" in text
        assert any(term in text for term in required_terms), f"{category}: {handle}"


@pytest.mark.parametrize(
    ("handle", "terms"),
    [
        ("workflow.local_expression.adapter.json", ("selectors", "set", "with{root:")),
        ("workflow.local_expression.adapter.key_value", ("with{root:", "no extra selector")),
        ("workflow.local_expression.adapter.markdown", ("heading", "add", "with{root:")),
        ("workflow.local_expression.adapter.text", ("lines", "replace", "with{root:")),
        ("workflow.local_expression.adapter.yaml", ("selectors", "no update action", "with{root:")),
        ("workflow.blocks", ("guards", "steps", "include")),
        ("workflow.branching", ("Guards", "`gate`", "`if`")),
        ("workflow.let", ("`let`", "`let.name`")),
        ("workflow.include_contract", ("`include`", "`with`", "validation")),
        ("workflow.value_expression_root.args", ("`args`", "`with`", "`inputs.name`")),
    ],
)
def test_workflow_class_guides_publish_syntax_navigation_and_boundaries(handle, terms):
    text = _text(handle)

    assert "Related surfaces" in text
    assert "Do not use for" in text
    for term in terms:
        assert term in text


@pytest.mark.parametrize("handle", sorted(WORKFLOW_RULE_EXAMPLE_FOCUSED_DESCRIBE_HUMAN))
def test_workflow_rule_examples_retain_executable_author_shapes(handle):
    human = human_mapping(WORKFLOW_RULE_EXAMPLE_FOCUSED_DESCRIBE_HUMAN[handle])
    examples = [
        example
        for section in human["sections"]
        for example in section.get("examples", [])
    ]

    assert examples
    assert all("```yaml" in example for example in examples)
    assert all("\n" in example for example in examples)


def _references(human):
    return [
        reference
        for section in human["sections"]
        for reference in section.get("references", [])
    ]


def test_workflow_rule_guides_publish_resolvable_related_surfaces():
    guides = workflow_rules_focused_describe_human([dict(rule) for rule in help_cli.WORKFLOW_AUTHORING_RULES])
    public_handles = set(help_cli.focused_describe_declarations())

    assert len(guides) == 25
    for handle, declaration in guides.items():
        references = _references(human_mapping(declaration))
        assert references, handle
        assert all(reference["handle"] in public_handles for reference in references), handle


def test_workflow_rule_example_guides_publish_resolvable_related_surfaces():
    public_handles = set(help_cli.focused_describe_declarations())

    assert len(WORKFLOW_RULE_EXAMPLE_FOCUSED_DESCRIBE_HUMAN) == 6
    for handle, declaration in WORKFLOW_RULE_EXAMPLE_FOCUSED_DESCRIBE_HUMAN.items():
        references = _references(human_mapping(declaration))
        assert references, handle
        assert all(reference["handle"] in public_handles for reference in references), handle


def test_routine_focused_guides_render_runnable_related_navigation():
    declarations = {
        handle: declaration
        for handle, declaration in help_cli.focused_describe_declarations().items()
        if handle.startswith("routine_contract")
    }

    for handle, declaration in declarations.items():
        human = human_mapping(declaration)
        rendered = help_cli._render_human(
            help_cli._focused_target_payload(handle, context=help_cli._HelpResponseContext())
        )
        for reference in _references(human):
            assert f"ordo-help describe {reference['handle']}" in rendered, handle
        inspect_next = next(
            (section.get("items", []) for section in human["sections"] if section["heading"] == "Inspect next"),
            [],
        )
        assert all(item.startswith("Run `ordo-help describe ") for item in inspect_next), handle


def test_local_expression_root_guides_use_reader_vocabulary_and_navigation():
    public_handles = set(help_cli.focused_describe_declarations())
    navigation_handles = (
        "workflow.local_expressions",
        "workflow.local_expression.adapter",
    )
    vocabulary_handles = [
        handle
        for handle in public_handles
        if handle in {"workflow.local_expressions", "workflow.local_expression.filter", "workflow.local_expression.builtin"}
        or handle.startswith(("workflow.local_expression.filter.", "workflow.local_expression.builtin."))
    ]

    for handle in vocabulary_handles:
        human = human_mapping(help_cli.focused_describe_declarations()[handle])
        text = str(human).lower()
        assert "function" not in text

    for handle in navigation_handles:
        human = human_mapping(help_cli.focused_describe_declarations()[handle])
        references = _references(human)
        assert references, handle
        assert all(reference["handle"] in public_handles for reference in references), handle


def test_workflow_contract_owns_the_complete_phase_three_batch():
    # The batch includes the 86 workflow-contract leaves and classes; rule
    # examples live beside their runtime-owned authoring-rule contract.
    handles = WORKFLOW_FOCUSED_DESCRIBE_HUMAN | WORKFLOW_ADDITIONAL_FOCUSED_DESCRIBE_HUMAN

    assert len(handles) == 86
    assert all(handle.startswith(("workflow.", "workflow_")) for handle in handles)
