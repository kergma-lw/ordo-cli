"""Shared entrypoints for workflow-local expressions by semantic context."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow

from .conditions import (
    AllCondition,
    AnyCondition,
    ConditionEvaluationNode,
    ConditionEvaluationReport,
    ExpressionCondition,
    NotCondition,
    normalize_condition_authoring,
)
from .local_expression_engine.core import ConditionObservationRequest, ConditionObservationResult, ReadOnlyObservationSession
from .local_expression_contexts import LocalExpressionContext, LocalExpressionContextFamily, LocalExpressionRoot, get_local_expression_context_policy
from .local_expression_engine.core import (
    EmbeddedValueExpressionNode,
    CallNode,
    ParsedLocalExpressionTree,
    ReferenceNode,
    StateReferenceNode,
    StepReferenceNode,
    ValueExpressionNode,
    collect_local_expression_dependencies,
    evaluate_condition_expression,
    evaluate_local_expression_tree,
    parse_local_expression_tree,
    LocalExpressionEvaluationError,
    LocalExpressionParseError,
    LocalExpressionValidationIssue,
    validate_local_expression_tree,
)


@dataclass(frozen=True, slots=True)
class ParsedLocalExpression:
    """Context-tagged parsed local expression.

    Runtime internals may still route through specialized parser/evaluator
    helpers, but callers enter through one local-expression surface keyed by
    semantic context.
    """

    context: LocalExpressionContext
    source: str
    root: EmbeddedValueExpressionNode
    value: ParsedLocalExpressionTree


LOCAL_EXPRESSION_PARSE_ERRORS = (LocalExpressionParseError,)
LocalExpressionValidationError = LocalExpressionValidationIssue


@dataclass(frozen=True, slots=True)
class LocalExpressionContextPolicyError:
    code: str
    message: str
    start: int
    end: int


def _local_expression_validation_prefix(context: LocalExpressionContext) -> str:
    return f"validation.workflow.local_expression.{context.value}"


def parse_local_expression(
    expression: str,
    *,
    context: LocalExpressionContext,
    allow_boolean_composition: bool | None = None,
) -> ParsedLocalExpression:
    """Parse one local expression through the shared context entrypoint."""

    policy = get_local_expression_context_policy(context)
    parsed = parse_local_expression_tree(
        expression,
        allow_boolean_composition=(policy.family is LocalExpressionContextFamily.CONDITION)
        if allow_boolean_composition is None
        else allow_boolean_composition,
    )
    return ParsedLocalExpression(context=context, source=expression, root=parsed.root, value=parsed)


def validate_parsed_local_expression(parsed: ParsedLocalExpression) -> tuple[LocalExpressionValidationError, ...]:
    """Validate one parsed local expression according to its context."""

    errors: list[LocalExpressionValidationError | LocalExpressionContextPolicyError] = []
    errors.extend(_validate_context_policy(parsed))
    errors.extend(validate_local_expression_tree(parsed.value))
    return tuple(errors)


def validate_parsed_local_expression_for_workflow(
    parsed: ParsedLocalExpression,
    workflow: Workflow,
) -> tuple[LocalExpressionValidationError, ...]:
    """Validate one parsed local expression with workflow-aware let expansion."""

    errors: list[LocalExpressionValidationError | LocalExpressionContextPolicyError] = []
    errors.extend(_validate_context_policy(parsed))
    errors.extend(validate_local_expression_tree(parsed.value, workflow=workflow, context=parsed.context))
    return tuple(errors)


def build_local_expression_parse_diagnostic(
    exc: LocalExpressionParseError,
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
    issue: LocalExpressionValidationError | LocalExpressionContextPolicyError,
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


@dataclass(frozen=True, slots=True)
class _LocalExpressionDependency:
    root: LocalExpressionRoot | None
    kind: str
    start: int
    end: int


def _validate_context_policy(parsed: ParsedLocalExpression) -> tuple[LocalExpressionContextPolicyError, ...]:
    policy = get_local_expression_context_policy(parsed.context)
    if not policy.whole_tree_restrictions:
        return ()
    errors: list[LocalExpressionContextPolicyError] = []
    seen: set[tuple[object, int, int]] = set()
    for dependency in _collect_local_expression_dependencies(parsed):
        if dependency.kind == "root" and dependency.root is not None and policy.allows_root(dependency.root):
            continue
        if dependency.kind == "observation":
            if policy.allows_observation:
                continue
            key = (dependency.kind, dependency.start, dependency.end)
            if key in seen:
                continue
            seen.add(key)
            errors.append(
                LocalExpressionContextPolicyError(
                    code=f"validation.workflow.local_expression.{parsed.context.value}.probe_ref",
                    message=f"read-only probe observations are not allowed in the {parsed.context.value} local-expression context",
                    start=dependency.start,
                    end=dependency.end,
                )
            )
            continue
        if dependency.root is None:
            continue
        assert dependency.root is not None
        key = (dependency.root, dependency.start, dependency.end)
        if key in seen:
            continue
        seen.add(key)
        errors.append(
            LocalExpressionContextPolicyError(
                code=f"validation.workflow.local_expression.{parsed.context.value}.{dependency.root.value}_ref",
                message=f"{dependency.root.value} references are not allowed in the {parsed.context.value} local-expression context",
                start=dependency.start,
                end=dependency.end,
            )
        )
    return tuple(errors)


def _collect_local_expression_dependencies(parsed: ParsedLocalExpression) -> tuple[_LocalExpressionDependency, ...]:
    return tuple(
        _LocalExpressionDependency(
            root=(None if dependency.kind == "observation" else (LocalExpressionRoot(dependency.name) if dependency.name in {root.value for root in LocalExpressionRoot} else None)),
            kind=dependency.kind,
            start=dependency.start,
            end=dependency.end,
        )
        for dependency in collect_local_expression_dependencies(parsed.value.root)
    )


def resolve_workflow_let_reference_node(
    node: EmbeddedValueExpressionNode,
    workflow: Workflow,
    *,
    context: LocalExpressionContext,
) -> ValueExpressionNode | None:
    """Resolve one workflow-level let reference into its bound expression tree when applicable."""

    if not isinstance(node, ReferenceNode) or not node.parts:
        return None
    binding_name = node.parts[0]
    expression = workflow.let_bindings.get(binding_name)
    if expression is None:
        return None
    parsed_binding = parse_local_expression(expression, context=context, allow_boolean_composition=context is not LocalExpressionContext.EMBEDDED_VALUE)
    binding_root = parsed_binding.value.root
    suffix = node.parts[1:]
    return _apply_workflow_let_suffix(binding_root, suffix)


def _apply_workflow_let_suffix(node: ValueExpressionNode, suffix: tuple[str, ...]) -> ValueExpressionNode:
    if not suffix:
        return node
    if isinstance(node, ReferenceNode):
        return ReferenceNode(start=node.start, end=node.end, parts=node.parts + suffix)
    if isinstance(node, StateReferenceNode):
        return StateReferenceNode(
            start=node.start,
            end=node.end,
            state_role=node.state_role,
            key_reference=node.key_reference,
            fields=node.fields + suffix,
        )
    if isinstance(node, StepReferenceNode):
        return StepReferenceNode(start=node.start, end=node.end, register=node.register, fields=node.fields + suffix)
    if isinstance(node, CallNode):
        return CallNode(start=node.start, end=node.end, target=node.target, arguments=node.arguments, fields=node.fields + suffix)
    return node


def extract_embedded_local_expression(value: str) -> str | None:
    """Extract the current `${...}` embedded local-expression surface."""

    if value.startswith("${") and value.endswith("}") and len(value) >= 4:
        return value[2:-1]
    return None


def parse_embedded_local_expression(
    value: str,
    *,
    context: LocalExpressionContext,
    allow_boolean_composition: bool | None = None,
) -> ParsedLocalExpression | None:
    """Parse one embedded local-expression surface for a non-native context."""

    expression = extract_embedded_local_expression(value)
    if expression is None:
        return None
    return parse_local_expression(expression, context=context, allow_boolean_composition=allow_boolean_composition)


def parse_embedded_value_local_expression(
    value: str,
    *,
    allow_boolean_composition: bool | None = None,
) -> ParsedLocalExpression | None:
    """Parse the embedded `${...}` surface in the standard value context."""

    return parse_embedded_local_expression(
        value,
        context=LocalExpressionContext.EMBEDDED_VALUE,
        allow_boolean_composition=allow_boolean_composition,
    )


def parse_value_local_expression(
    value: str,
    *,
    context: LocalExpressionContext = LocalExpressionContext.EMBEDDED_VALUE,
    allow_boolean_composition: bool | None = None,
) -> ParsedLocalExpression:
    """Parse one value-oriented local-expression surface.

    Value contexts accept plain bare expressions and, for compatibility,
    the older embedded `${...}` surface.
    """

    expression = extract_embedded_local_expression(value)
    if expression is not None:
        return parse_local_expression(expression, context=context, allow_boolean_composition=allow_boolean_composition)
    return parse_local_expression(value, context=context, allow_boolean_composition=allow_boolean_composition)


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
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    """Evaluate one parsed local expression through the shared context API."""

    if parsed.value is None:
        raise LocalExpressionEvaluationError(
            code="runtime.local_expression.evaluation_unsupported",
            message=f"Local-expression context '{parsed.context.value}' is not directly evaluable through the canonical local-expression engine",
            details={"context": parsed.context.value},
        )
    return evaluate_local_expression_tree(
        parsed.value,
        workflow,
        context=parsed.context,
        step_results={} if step_results is None else step_results,
        observation_session=observation_session,
    )


def evaluate_parsed_value_local_expression(
    parsed: ParsedLocalExpression,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    """Evaluate one parsed local expression in the standard value context."""

    if parsed.context is not LocalExpressionContext.EMBEDDED_VALUE:
        raise LocalExpressionEvaluationError(
            code="runtime.local_expression.context_mismatch",
            message="Embedded value evaluation expects the embedded-value context",
            details={"context": parsed.context.value},
        )
    return evaluate_parsed_local_expression(
        parsed,
        workflow,
        step_results=step_results,
        observation_session=observation_session,
    )


def resolve_embedded_local_expression(
    value: str,
    workflow: Workflow,
    *,
    context: LocalExpressionContext,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
    allow_boolean_composition: bool | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    """Resolve one embedded local-expression surface through the shared context API."""

    from .value_resolution import ValueResolutionError

    try:
        parsed = parse_embedded_local_expression(
            value,
            context=context,
            allow_boolean_composition=allow_boolean_composition,
        )
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
        return evaluate_parsed_local_expression(
            parsed,
            workflow,
            step_results=step_results,
            observation_session=observation_session,
        )
    except LocalExpressionEvaluationError as exc:
        raise ValueResolutionError(code=exc.code, message=exc.message, details=exc.details) from exc


def resolve_embedded_value_local_expression(
    value: str,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
    allow_boolean_composition: bool | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    """Resolve the embedded `${...}` surface in the standard value context."""

    return resolve_embedded_local_expression(
        value,
        workflow,
        context=LocalExpressionContext.EMBEDDED_VALUE,
        step_results=step_results,
        allow_boolean_composition=allow_boolean_composition,
        observation_session=observation_session,
    )


def resolve_value_local_expression(
    value: str,
    workflow: Workflow,
    *,
    context: LocalExpressionContext = LocalExpressionContext.EMBEDDED_VALUE,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
    allow_boolean_composition: bool | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    """Resolve one value-oriented local-expression surface.

    Value contexts accept plain bare expressions and the embedded `${...}`
    compatibility form.
    """

    from .value_resolution import ValueResolutionError

    try:
        parsed = parse_value_local_expression(
            value,
            context=context,
            allow_boolean_composition=allow_boolean_composition,
        )
    except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
        expression = extract_embedded_local_expression(value)
        visible = value if expression is None else expression
        raise ValueResolutionError(
            code="runtime.local_expression.syntax",
            message=exc.message,
            details={"context": context.value, "position": exc.position, "end": exc.end if exc.end is not None else exc.position, "expression": visible},
        ) from exc
    try:
        return evaluate_parsed_local_expression(
            parsed,
            workflow,
            step_results=step_results,
            observation_session=observation_session,
        )
    except LocalExpressionEvaluationError as exc:
        raise ValueResolutionError(code=exc.code, message=exc.message, details=exc.details) from exc


def resolve_condition_local_expression(
    value: str,
    workflow: Workflow,
    *,
    context: LocalExpressionContext,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
    observe: Callable[[ConditionObservationRequest], ConditionObservationResult] | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
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
    condition_tree = parsed.value
    if condition_tree is not None and (observation_session is not None or observe is not None):
        evaluation = evaluate_condition_expression(
            condition_tree,
            workflow,
            context=context,
            observe=observe,
            session=observation_session,
            step_results=step_results,
        )
        if evaluation.status != "ok":
            if evaluation.diagnostics:
                first = evaluation.diagnostics[0]
                raise ValueResolutionError(
                    code=first.code,
                    message=first.message,
                    details=first.details,
                )
            raise ValueResolutionError(
                code="runtime.local_expression.probe_failed",
                message="Condition local expression could not be evaluated safely",
                details={
                    "context": context.value,
                    "expression": value,
                    "diagnostic_codes": [diagnostic.code for diagnostic in evaluation.diagnostics],
                },
            )
        return evaluation.value
    try:
        return evaluate_parsed_local_expression(parsed, workflow, step_results=step_results)
    except LocalExpressionEvaluationError as exc:
        raise ValueResolutionError(code=exc.code, message=exc.message, details=exc.details) from exc


def resolve_condition_value(
    value: JSONValue,
    workflow: Workflow,
    *,
    context: LocalExpressionContext,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
    observe: Callable[[ConditionObservationRequest], ConditionObservationResult] | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    """Resolve one authored string or structured condition surface."""

    return _resolve_condition_node(
        normalize_condition_authoring(value),
        workflow,
        context=context,
        step_results=step_results,
        observe=observe,
        observation_session=observation_session,
    )


def evaluate_condition_report(
    value: JSONValue,
    workflow: Workflow,
    *,
    context: LocalExpressionContext,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
    observe: Callable[[ConditionObservationRequest], ConditionObservationResult] | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
    field_name: str = "if",
) -> ConditionEvaluationReport:
    """Evaluate one authored condition surface with full diagnostics."""

    root = _evaluate_condition_node_report(
        normalize_condition_authoring(value, field_name=field_name),
        workflow,
        context=context,
        step_results=step_results,
        observe=observe,
        observation_session=observation_session,
    )
    failed, unknown, passed = _collect_condition_leaves(root)
    return ConditionEvaluationReport(
        verdict=root.verdict,
        root=root,
        field_name=field_name,
        failed=tuple(failed),
        unknown=tuple(unknown),
        passed=tuple(passed),
    )


def _collect_condition_leaves(
    node: ConditionEvaluationNode,
) -> tuple[list[ConditionEvaluationNode], list[ConditionEvaluationNode], list[ConditionEvaluationNode]]:
    failed: list[ConditionEvaluationNode] = []
    unknown: list[ConditionEvaluationNode] = []
    passed: list[ConditionEvaluationNode] = []

    def visit(current: ConditionEvaluationNode) -> None:
        if not current.children:
            if current.verdict == "failed":
                failed.append(current)
            elif current.verdict == "unknown":
                unknown.append(current)
            elif current.verdict == "passed":
                passed.append(current)
            return
        for child in current.children:
            visit(child)

    visit(node)
    return failed, unknown, passed


def _evaluate_condition_node_report(
    node: ExpressionCondition | AllCondition | AnyCondition | NotCondition,
    workflow: Workflow,
    *,
    context: LocalExpressionContext,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
    observe: Callable[[ConditionObservationRequest], ConditionObservationResult] | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
    path: tuple[str, ...] = (),
) -> ConditionEvaluationNode:
    from .value_resolution import ValueResolutionError

    if isinstance(node, ExpressionCondition):
        try:
            value = resolve_condition_local_expression(
                node.expression,
                workflow,
                context=context,
                step_results=step_results,
                observe=observe,
                observation_session=observation_session,
            )
        except ValueResolutionError as exc:
            return ConditionEvaluationNode(
                kind="expression",
                verdict="unknown",
                path=path,
                expression=node.expression,
                message=exc.message,
                code=exc.code,
            )
        if not isinstance(value, bool):
            return ConditionEvaluationNode(
                kind="expression",
                verdict="unknown",
                path=path,
                expression=node.expression,
                message="Condition must evaluate to a boolean value",
                code="runtime.step.condition.result_type",
            )
        return ConditionEvaluationNode(
            kind="expression",
            verdict="passed" if value else "failed",
            path=path,
            expression=node.expression,
            value=value,
        )
    if isinstance(node, AllCondition):
        child_path_prefix = () if node.implicit else ("all",)
        children = tuple(
            _evaluate_condition_node_report(
                item,
                workflow,
                context=context,
                step_results=step_results,
                observe=observe,
                observation_session=observation_session,
                path=path + child_path_prefix + (str(index),),
            )
            for index, item in enumerate(node.items)
        )
        if any(child.verdict == "failed" for child in children):
            verdict = "failed"
        elif any(child.verdict == "unknown" for child in children):
            verdict = "unknown"
        else:
            verdict = "passed"
        return ConditionEvaluationNode(kind="all", verdict=verdict, path=path, children=children)
    if isinstance(node, AnyCondition):
        children = tuple(
            _evaluate_condition_node_report(
                item,
                workflow,
                context=context,
                step_results=step_results,
                observe=observe,
                observation_session=observation_session,
                path=path + ("any", str(index)),
            )
            for index, item in enumerate(node.items)
        )
        if any(child.verdict == "passed" for child in children):
            verdict = "passed"
        elif any(child.verdict == "unknown" for child in children):
            verdict = "unknown"
        else:
            verdict = "failed"
        return ConditionEvaluationNode(kind="any", verdict=verdict, path=path, children=children)
    child = _evaluate_condition_node_report(
        node.item,
        workflow,
        context=context,
        step_results=step_results,
        observe=observe,
        observation_session=observation_session,
        path=path + ("not",),
    )
    if child.verdict == "unknown":
        verdict = "unknown"
    elif child.verdict == "passed":
        verdict = "failed"
    else:
        verdict = "passed"
    return ConditionEvaluationNode(kind="not", verdict=verdict, path=path, children=(child,))


def _resolve_condition_node(
    node: ExpressionCondition | AllCondition | AnyCondition | NotCondition,
    workflow: Workflow,
    *,
    context: LocalExpressionContext,
    step_results: dict[str, OperationResult | JSONValue] | None = None,
    observe: Callable[[ConditionObservationRequest], ConditionObservationResult] | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    if isinstance(node, ExpressionCondition):
        return resolve_condition_local_expression(
            node.expression,
            workflow,
            context=context,
            step_results=step_results,
            observe=observe,
            observation_session=observation_session,
        )
    if isinstance(node, AllCondition):
        for item in node.items:
            result = _resolve_condition_node(
                item,
                workflow,
                context=context,
                step_results=step_results,
                observe=observe,
                observation_session=observation_session,
            )
            if not isinstance(result, bool):
                return result
            if result is False:
                return False
        return True
    if isinstance(node, AnyCondition):
        for item in node.items:
            result = _resolve_condition_node(
                item,
                workflow,
                context=context,
                step_results=step_results,
                observe=observe,
                observation_session=observation_session,
            )
            if not isinstance(result, bool):
                return result
            if result is True:
                return True
        return False
    result = _resolve_condition_node(
        node.item,
        workflow,
        context=context,
        step_results=step_results,
        observe=observe,
        observation_session=observation_session,
    )
    if not isinstance(result, bool):
        return result
    return not result
