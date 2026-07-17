"""Shared entrypoints for workflow-local expressions by semantic context."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow

from .guard_expressions import (
    GuardExpressionNode,
    GuardExpressionParseError,
    GuardExpressionValidationError,
    ParsedGuardExpression,
    parse_guard_expression,
    validate_parsed_guard_expression,
)
from .local_expression_contexts import LocalExpressionContext, LocalExpressionContextFamily, get_local_expression_context_policy
from .value_expressions import ParsedValueExpression, ValueExpressionEvaluationError, ValueExpressionNode, ValueExpressionParseError, evaluate_value_expression, parse_value_expression


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


def _local_expression_validation_prefix(context: LocalExpressionContext) -> str:
    return f"validation.workflow.local_expression.{context.value}"


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


def build_local_expression_parse_diagnostic(
    exc: GuardExpressionParseError | ValueExpressionParseError,
    *,
    context: LocalExpressionContext,
    path: tuple[str, ...],
    source: str,
    expression: str,
) -> Diagnostic:
    snippet = expression[exc.position : exc.end if exc.end is not None else exc.position + 1]
    return Diagnostic(
        code=f"{_local_expression_validation_prefix(context)}.syntax",
        level="error",
        message=exc.message,
        path=path,
        details={
            "source": source,
            "position": exc.position,
            "end": exc.end if exc.end is not None else exc.position,
            "snippet": snippet,
            "expression": expression,
            "context": context.value,
        },
    )


def build_local_expression_validation_diagnostic(
    issue: LocalExpressionValidationError,
    *,
    context: LocalExpressionContext,
    path: tuple[str, ...],
    source: str,
    expression: str,
) -> Diagnostic:
    suffix = issue.code.rsplit(".", 1)[-1]
    return Diagnostic(
        code=f"{_local_expression_validation_prefix(context)}.{suffix}",
        level="error",
        message=issue.message,
        path=path,
        details={
            "source": source,
            "position": issue.start,
            "end": issue.end,
            "snippet": expression[issue.start : issue.end],
            "expression": expression,
            "context": context.value,
        },
    )


def extract_embedded_local_expression(value: str) -> str | None:
    """Extract the current `${...}` embedded local-expression surface."""

    if value.startswith("${") and value.endswith("}") and len(value) >= 4:
        return value[2:-1]
    return None


def parse_embedded_local_expression(value: str, *, context: LocalExpressionContext) -> ParsedLocalExpression | None:
    """Parse one embedded local-expression surface for a non-native context."""

    expression = extract_embedded_local_expression(value)
    if expression is None:
        return None
    return parse_local_expression(expression, context=context)


def parse_condition_local_expression(value: str, *, context: LocalExpressionContext) -> ParsedLocalExpression:
    """Parse one condition-oriented local-expression surface.

    Condition contexts accept native bare expressions and, for compatibility,
    the older embedded `${...}` surface.
    """

    expression = extract_embedded_local_expression(value)
    if expression is not None:
        return parse_local_expression(expression, context=context)
    return parse_local_expression(value, context=context, allow_boolean_composition=True)


def evaluate_parsed_local_expression(
    parsed: ParsedLocalExpression,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
) -> JSONValue:
    """Evaluate one parsed local expression through the shared context API."""

    if parsed.value is None:
        raise ValueExpressionEvaluationError(
            code="runtime.local_expression.evaluation_unsupported",
            message=f"Local-expression context '{parsed.context.value}' is not directly evaluable through the value-expression runtime",
            details={"context": parsed.context.value},
        )
    return evaluate_value_expression(parsed.value, workflow, step_results={} if step_results is None else step_results)


def resolve_embedded_local_expression(
    value: str,
    workflow: Workflow,
    *,
    context: LocalExpressionContext,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
) -> JSONValue:
    """Resolve one embedded local-expression surface through the shared context API."""

    from .value_resolution import ValueResolutionError

    try:
        parsed = parse_embedded_local_expression(value, context=context)
    except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
        raise ValueResolutionError(
            code="runtime.local_expression.syntax",
            message=exc.message,
            details={"context": context.value, "position": exc.position, "end": exc.end if exc.end is not None else exc.position},
        ) from exc
    if parsed is None:
        raise ValueResolutionError(
            code="runtime.local_expression.embedding_required",
            message=f"Local-expression context '{context.value}' requires the current embedded '${{...}}' surface",
            details={"context": context.value},
        )
    try:
        return evaluate_parsed_local_expression(parsed, workflow, step_results=step_results)
    except ValueExpressionEvaluationError as exc:
        raise ValueResolutionError(code=exc.code, message=exc.message, details=exc.details) from exc


def resolve_condition_local_expression(
    value: str,
    workflow: Workflow,
    *,
    context: LocalExpressionContext,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
) -> JSONValue:
    """Resolve one condition-oriented local-expression surface.

    Condition contexts accept native bare expressions and the embedded `${...}`
    compatibility form.
    """

    from .value_resolution import ValueResolutionError

    try:
        parsed = parse_condition_local_expression(value, context=context)
    except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
        expression = extract_embedded_local_expression(value)
        visible = value if expression is None else expression
        raise ValueResolutionError(
            code="runtime.local_expression.syntax",
            message=exc.message,
            details={"context": context.value, "position": exc.position, "end": exc.end if exc.end is not None else exc.position, "expression": visible},
        ) from exc
    try:
        return evaluate_parsed_local_expression(parsed, workflow, step_results=step_results)
    except ValueExpressionEvaluationError as exc:
        raise ValueResolutionError(code=exc.code, message=exc.message, details=exc.details) from exc
