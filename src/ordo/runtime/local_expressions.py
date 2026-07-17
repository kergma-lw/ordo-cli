"""Shared entrypoints for workflow-local expressions by semantic context."""

from __future__ import annotations

from dataclasses import dataclass

from .guard_expressions import (
    GuardExpressionNode,
    GuardExpressionParseError,
    GuardExpressionValidationError,
    ParsedGuardExpression,
    parse_guard_expression,
    validate_parsed_guard_expression,
)
from .local_expression_contexts import LocalExpressionContext, LocalExpressionContextFamily, get_local_expression_context_policy
from .value_expressions import ParsedValueExpression, ValueExpressionNode, ValueExpressionParseError, parse_value_expression


@dataclass(frozen=True, slots=True)
class ParsedLocalExpression:
    """Context-tagged parsed local expression.

    Phase 2 still delegates to legacy parsers internally, but callers stop
    talking directly to separate guard/value axes and instead enter through one
    local-expression surface keyed by context.
    """

    context: LocalExpressionContext
    source: str
    root: GuardExpressionNode | ValueExpressionNode
    guard: ParsedGuardExpression | None = None
    value: ParsedValueExpression | None = None


LOCAL_EXPRESSION_PARSE_ERRORS = (GuardExpressionParseError, ValueExpressionParseError)
LocalExpressionValidationError = GuardExpressionValidationError


def parse_local_expression(
    expression: str,
    *,
    context: LocalExpressionContext,
    allow_boolean_composition: bool | None = None,
) -> ParsedLocalExpression:
    """Parse one local expression through the shared context entrypoint."""

    if context is LocalExpressionContext.GUARD:
        parsed = parse_guard_expression(expression)
        return ParsedLocalExpression(context=context, source=expression, root=parsed.root, guard=parsed)

    policy = get_local_expression_context_policy(context)
    parsed = parse_value_expression(
        expression,
        allow_boolean_composition=(policy.family is LocalExpressionContextFamily.CONDITION)
        if allow_boolean_composition is None
        else allow_boolean_composition,
    )
    return ParsedLocalExpression(context=context, source=expression, root=parsed.root, value=parsed)


def validate_parsed_local_expression(parsed: ParsedLocalExpression) -> tuple[LocalExpressionValidationError, ...]:
    """Validate one parsed local expression according to its context."""

    if parsed.context is LocalExpressionContext.GUARD:
        assert parsed.guard is not None
        return validate_parsed_guard_expression(parsed.guard)
    return ()
