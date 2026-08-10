"""Canonical parser and evaluator for the shared local-expression engine."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import re
from typing import TYPE_CHECKING, Literal

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONScalar, JSONValue
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow

from ..state import RuntimeStateError, read_state_document, read_state_value, resolve_state_target, resolve_workflow_input_reference
from ..representation_adapters import (
    RepresentationAdapterError,
    RepresentationAdapterInvocation,
    RepresentationAdapterResult,
    evaluate_representation_adapter_invocation,
    has_representation_adapter,
)
from ..boolean_composition import parse_boolean_and, parse_boolean_not, parse_boolean_or
from .registry import (
    ValueExpressionBuiltinSpec,
    ValueExpressionFilterSpec,
    build_builtin_registry,
    build_filter_registry,
)

if TYPE_CHECKING:
    from .registry import ValueExpressionBuiltinSpec, ValueExpressionFilterSpec


@dataclass(frozen=True, slots=True)
class ValueExpressionNode:
    """Base parsed local-expression node."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class LiteralNode(ValueExpressionNode):
    """Scalar literal used inside a value expression."""

    value: JSONScalar


@dataclass(frozen=True, slots=True)
class ReferenceNode(ValueExpressionNode):
    """Direct dotted reference such as ``inputs.title``."""

    parts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StateReferenceNode(ValueExpressionNode):
    """Runtime-state read such as ``state.task_memory[inputs.task_key].branch``."""

    state_role: str
    key_reference: tuple[str, ...]
    fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StepReferenceNode(ValueExpressionNode):
    """Prior registered step result read such as ``step.issue.outputs.id``."""

    register: str
    fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ListNode(ValueExpressionNode):
    """List literal used inside a local expression."""

    items: tuple[ValueExpressionNode, ...] = ()


@dataclass(frozen=True, slots=True)
class ObjectEntryNode(ValueExpressionNode):
    """One object-literal entry used inside a local expression."""

    key: str
    value: ValueExpressionNode


@dataclass(frozen=True, slots=True)
class ObjectNode(ValueExpressionNode):
    """Object literal used inside a local expression."""

    entries: tuple[ObjectEntryNode, ...] = ()


@dataclass(frozen=True, slots=True)
class CallArgumentNode(ValueExpressionNode):
    """Named argument passed to a read-only probe call."""

    name: str
    value: ValueExpressionNode


@dataclass(frozen=True, slots=True)
class CallNode(ValueExpressionNode):
    """Read-only dotted call such as ``gh.issue(repository=inputs.repository)``."""

    target: ReferenceNode
    arguments: tuple[CallArgumentNode, ...] = ()
    fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FilterApplicationNode(ValueExpressionNode):
    """One built-in filter stage inside a pipe chain."""

    name: str
    arguments: tuple[ValueExpressionNode, ...] = ()


@dataclass(frozen=True, slots=True)
class OnlyPredicateNode(ValueExpressionNode):
    """One bounded item-filter predicate used by ``only(...)``."""

    path: str
    operator: Literal["=", "!="]
    expected: ValueExpressionNode


@dataclass(frozen=True, slots=True)
class PipelineNode(ValueExpressionNode):
    """Left-to-right pipeline of built-in filters over a source value."""

    source: ValueExpressionNode
    filters: tuple[ValueExpressionNode, ...] = ()


@dataclass(frozen=True, slots=True)
class BuiltinCallNode(ValueExpressionNode):
    """Root built-in call such as ``format(...)``."""

    name: str
    arguments: tuple[ValueExpressionNode, ...] = ()


@dataclass(frozen=True, slots=True)
class UnaryNode(ValueExpressionNode):
    """Unary boolean operator inside a step-condition expression."""

    operator: Literal["not"]
    operand: ValueExpressionNode


@dataclass(frozen=True, slots=True)
class BinaryNode(ValueExpressionNode):
    """Binary boolean or comparison operator inside a local expression."""

    operator: Literal["and", "or", "==", "!=", "in", "not in"]
    left: ValueExpressionNode
    right: ValueExpressionNode


@dataclass(frozen=True, slots=True)
class AdapterBindingNode(ValueExpressionNode):
    """One host-owned outer parameter binding for an adapter invocation."""

    name: str
    value: ValueExpressionNode


@dataclass(frozen=True, slots=True)
class AdapterInvocationNode(ValueExpressionNode):
    """One representation-adapter invocation with family-owned body."""

    family: str
    body: str
    bindings: tuple[AdapterBindingNode, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedLocalExpressionTree:
    """Structured parsed representation of one canonical local-expression tree."""

    source: str
    root: ValueExpressionNode


@dataclass(frozen=True, slots=True)
class LocalExpressionParseError(Exception):
    """Structured parser error suitable for workflow diagnostics."""

    message: str
    position: int
    end: int | None = None

    def to_diagnostic(self, *, path: tuple[str, ...], source: str, expression: str) -> Diagnostic:
        snippet = expression[self.position : self.end if self.end is not None else self.position + 1]
        return Diagnostic(
            code="validation.workflow.value_expr.syntax",
            level="error",
            message=self.message,
            path=path,
            details={
                "source": source,
                "position": self.position,
                "end": self.end if self.end is not None else self.position,
                "snippet": snippet,
                "expression": expression,
            },
        )


@dataclass(frozen=True, slots=True)
class LocalExpressionEvaluationError(Exception):
    """Structured evaluation error for canonical local-expression trees."""

    code: str
    message: str
    details: JSONObject

    def to_diagnostic(self, *, path: tuple[str, ...] = ()) -> Diagnostic:
        return Diagnostic(
            code=self.code,
            level="error",
            message=self.message,
            path=path,
            details=dict(self.details),
        )


@dataclass(frozen=True, slots=True)
class LocalExpressionValidationIssue:
    """Structured semantic validation issue for canonical local-expression trees."""

    code: str
    message: str
    start: int
    end: int

    def to_diagnostic(self, *, path: tuple[str, ...], source: str, expression: str) -> Diagnostic:
        return Diagnostic(
            code=self.code,
            level="error",
            message=self.message,
            path=path,
            details={
                "source": source,
                "position": self.start,
                "end": self.end,
                "snippet": expression[self.start : self.end],
                "expression": expression,
            },
        )


@dataclass(frozen=True, slots=True)
class LocalExpressionDependency:
    """One dependency reference collected from the canonical expression tree."""

    kind: Literal["root", "observation"]
    name: str
    start: int
    end: int


# Transitional aliases retained while runtime callers move to canonical terminology.
LocalExpressionNode = ValueExpressionNode
ParsedValueExpression = ParsedLocalExpressionTree
ValueExpressionParseError = LocalExpressionParseError
ValueExpressionEvaluationError = LocalExpressionEvaluationError


@dataclass(frozen=True, slots=True)
class _FieldPathSyntaxError(Exception):
    message: str
    position: int


FieldPathSegment = str | int
_FIELD_PATH_MISSING = object()
ValueExpressionValidationError = LocalExpressionValidationIssue
ValueExpressionDependency = LocalExpressionDependency


@dataclass(frozen=True, slots=True)
class ConditionObservationRequest:
    """One read-only probe observation requested by canonical condition evaluation."""

    expression_text: str
    target: tuple[str, ...]
    fields: tuple[str, ...] = ()
    arguments: tuple[tuple[str, JSONValue], ...] = ()


@dataclass(frozen=True, slots=True)
class ConditionObservationResult:
    """One read-only probe observation result returned to canonical evaluation."""

    status: Literal["ok", "probe_failed"]
    value: JSONValue | None
    diagnostics: tuple[Diagnostic, ...] = ()
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class ConditionTraceEntry:
    """One trace item emitted by canonical condition evaluation."""

    expr: str
    kind: str
    status: str
    value: JSONValue | None = None
    operator: str | None = None
    left: JSONValue | None = None
    right: JSONValue | None = None
    reference: str | None = None

    def to_contract(self) -> JSONObject:
        payload: JSONObject = {"expr": self.expr, "kind": self.kind, "status": self.status, "value": self.value}
        if self.operator is not None:
            payload["operator"] = self.operator
        if self.left is not None:
            payload["left"] = self.left
        if self.right is not None:
            payload["right"] = self.right
        if self.reference is not None:
            payload["reference"] = self.reference
        return payload


@dataclass(frozen=True, slots=True)
class ConditionEvaluationResult:
    """Canonical condition-evaluation result over the shared local-expression AST."""

    status: Literal["ok", "probe_failed"]
    value: JSONValue | None
    diagnostics: tuple[Diagnostic, ...] = ()
    trace: tuple[ConditionTraceEntry, ...] = ()
    cache_entries: int = 0


@dataclass(frozen=True, slots=True)
class ObservationSessionResult:
    """One read-only observation outcome returned by a shared session."""

    result: ConditionObservationResult
    cached: bool


class ReadOnlyObservationSession:
    """Shared cache/session for read-only local-expression observations."""

    def __init__(
        self,
        observe: Callable[[ConditionObservationRequest], ConditionObservationResult],
    ) -> None:
        self._observe = observe
        self._cache: dict[str, ConditionObservationResult] = {}

    def observe(self, request: ConditionObservationRequest) -> ObservationSessionResult:
        cache_key = self._cache_key(request)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return ObservationSessionResult(result=cached, cached=True)
        result = self._observe(request)
        self._cache[cache_key] = result
        return ObservationSessionResult(result=result, cached=False)

    @property
    def cache_entries(self) -> int:
        return len(self._cache)

    def _cache_key(self, request: ConditionObservationRequest) -> str:
        payload = {
            "target": list(request.target),
            "fields": list(request.fields),
            "arguments": [
                {"name": name, "value": value}
                for name, value in sorted(request.arguments, key=lambda item: item[0])
            ],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    start: int
    end: int


def parse_local_expression_tree(expression: str, *, allow_boolean_composition: bool = False) -> ParsedLocalExpressionTree:
    """Parse one canonical local-expression tree from authored text."""

    adapter_node = _try_parse_adapter_invocation(expression, allow_boolean_composition=allow_boolean_composition)
    if adapter_node is not None:
        return ParsedLocalExpressionTree(source=expression, root=adapter_node)

    parser = _Parser(expression, allow_boolean_composition=allow_boolean_composition)
    root = parser.parse()
    return ParsedLocalExpressionTree(source=expression, root=root)


def evaluate_local_expression_tree(
    parsed: ParsedLocalExpressionTree,
    workflow: Workflow,
    *,
    context=None,
    step_results: dict[str, OperationResult] | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    """Evaluate one canonical local-expression tree against workflow-visible data."""

    if context is None:
        from ordo.runtime.local_expression_contexts import LocalExpressionContext

        context = LocalExpressionContext.EMBEDDED_VALUE

    return _evaluate_node(
        parsed.root,
        parsed=parsed,
        workflow=workflow,
        context=context,
        step_results={} if step_results is None else step_results,
        observation_session=observation_session,
    )


def evaluate_condition_expression(
    parsed: ParsedLocalExpressionTree,
    workflow: Workflow,
    *,
    context=None,
    observe: Callable[[ConditionObservationRequest], ConditionObservationResult] | None = None,
    session: ReadOnlyObservationSession | None = None,
    step_results: dict[str, OperationResult | JSONObject] | None = None,
) -> ConditionEvaluationResult:
    """Evaluate a canonical condition expression, including read-only probe observations."""

    if session is None:
        if observe is None:
            raise ValueError("Condition evaluation requires either an observation session or an observe callback")
        session = ReadOnlyObservationSession(observe)
    if context is None:
        from ordo.runtime.local_expression_contexts import LocalExpressionContext

        context = LocalExpressionContext.STEP_CONDITION
    evaluator = _ConditionEvaluator(
        parsed,
        workflow,
        context=context,
        observation_session=session,
        step_results={} if step_results is None else step_results,
    )
    return evaluator.evaluate()


def validate_local_expression_tree(
    parsed: ParsedLocalExpressionTree,
    *,
    workflow: Workflow | None = None,
    context: LocalExpressionContext | None = None,
) -> tuple[LocalExpressionValidationIssue, ...]:
    """Validate semantic rules over the canonical local-expression tree."""

    validator = _SemanticValidator(parsed, workflow=workflow, context=context)
    return tuple(validator.validate())


def collect_local_expression_dependencies(node: ValueExpressionNode) -> tuple[LocalExpressionDependency, ...]:
    """Collect local-root dependencies from the canonical local-expression tree."""

    found: list[LocalExpressionDependency] = []

    def visit(current: ValueExpressionNode) -> None:
        if isinstance(current, ReferenceNode):
            if current.parts and current.parts[0] in {"inputs", "args", "item", "state", "step"}:
                found.append(LocalExpressionDependency(kind="root", name=current.parts[0], start=current.start, end=current.end))
            elif current.parts and len(current.parts) > 1:
                found.append(LocalExpressionDependency(kind="observation", name="probe", start=current.start, end=current.end))
            elif current.parts:
                found.append(LocalExpressionDependency(kind="root", name=current.parts[0], start=current.start, end=current.end))
            return
        if isinstance(current, StateReferenceNode):
            found.append(LocalExpressionDependency(kind="root", name="state", start=current.start, end=current.end))
            return
        if isinstance(current, StepReferenceNode):
            found.append(LocalExpressionDependency(kind="root", name="step", start=current.start, end=current.end))
            return
        if isinstance(current, ListNode):
            for item in current.items:
                visit(item)
            return
        if isinstance(current, ObjectEntryNode):
            visit(current.value)
            return
        if isinstance(current, ObjectNode):
            for entry in current.entries:
                visit(entry)
            return
        if isinstance(current, CallArgumentNode):
            visit(current.value)
            return
        if isinstance(current, CallNode):
            found.append(LocalExpressionDependency(kind="observation", name="probe", start=current.start, end=current.end))
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, PipelineNode):
            visit(current.source)
            for item in current.filters:
                visit(item)
            return
        if isinstance(current, FilterApplicationNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, BuiltinCallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, UnaryNode):
            visit(current.operand)
            return
        if isinstance(current, BinaryNode):
            visit(current.left)
            visit(current.right)
            return
        if isinstance(current, AdapterBindingNode):
            visit(current.value)
            return
        if isinstance(current, AdapterInvocationNode):
            for binding in current.bindings:
                visit(binding)
            return

    visit(node)
    return tuple(found)


def _try_parse_adapter_invocation(expression: str, *, allow_boolean_composition: bool) -> AdapterInvocationNode | None:
    adapter_node = _try_parse_adapter_invocation_at(
        expression,
        start=0,
        allow_boolean_composition=allow_boolean_composition,
    )
    if adapter_node is None:
        return None
    end = adapter_node.end
    trailing = expression[end:]
    if trailing.strip():
        token_start = end + len(trailing) - len(trailing.lstrip())
        raise ValueExpressionParseError("Unexpected trailing token", token_start, len(expression))
    return adapter_node


def _try_parse_adapter_invocation_at(
    expression: str,
    *,
    start: int,
    allow_boolean_composition: bool,
    stop_chars: str = "",
    allow_empty_body: bool = False,
) -> AdapterInvocationNode | None:
    if start >= len(expression) or not (expression[start].isalpha() or expression[start] == "_"):
        return None

    family_end = start + 1
    while family_end < len(expression) and (expression[family_end].isalnum() or expression[family_end] == "_"):
        family_end += 1
    family = expression[start:family_end]
    if family in {"inputs", "args", "state", "step", "true", "false", "null", "not", "in"}:
        return None

    probe = family_end
    while probe < len(expression) and expression[probe].isspace():
        probe += 1
    if allow_empty_body and has_representation_adapter(family) and (probe >= len(expression) or (stop_chars and expression[probe] in stop_chars)):
        return AdapterInvocationNode(start=start, end=family_end, family=family, body="", bindings=())
    if probe >= len(expression):
        return None
    if text_starts := expression.startswith("with{", probe):
        if not has_representation_adapter(family):
            return None
    elif expression[probe] not in "[{.-":
        return None
    if not text_starts and expression[probe] in ".-" and not has_representation_adapter(family):
        return None
    if not text_starts and expression[probe] == "-" and not expression.startswith("->", probe):
        return None

    body, bindings, end = _split_adapter_body_and_bindings(
        expression,
        body_start=family_end,
        allow_boolean_composition=allow_boolean_composition,
        stop_chars=stop_chars,
    )
    return AdapterInvocationNode(start=start, end=end, family=family, body=body, bindings=bindings)


def _split_adapter_body_and_bindings(
    text: str,
    *,
    body_start: int,
    allow_boolean_composition: bool,
    stop_chars: str = "",
) -> tuple[str, tuple[AdapterBindingNode, ...], int]:
    position = body_start
    depth_paren = 0
    depth_bracket = 0
    depth_brace = 0
    quote: str | None = None
    escape = False
    while position < len(text):
        char = text[position]
        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            position += 1
            continue
        if char in {'"', "'"}:
            quote = char
            position += 1
            continue
        if stop_chars and depth_paren == 0 and depth_bracket == 0 and depth_brace == 0 and char in stop_chars:
            return text[body_start:position].rstrip(), (), position
        if char == "(":
            depth_paren += 1
            position += 1
            continue
        if char == ")":
            depth_paren -= 1
            if depth_paren < 0:
                raise ValueExpressionParseError("Unexpected ')' in adapter body", position, position + 1)
            position += 1
            continue
        if char == "[":
            depth_bracket += 1
            position += 1
            continue
        if char == "]":
            depth_bracket -= 1
            if depth_bracket < 0:
                raise ValueExpressionParseError("Unexpected ']' in adapter body", position, position + 1)
            position += 1
            continue
        if char == "{":
            depth_brace += 1
            position += 1
            continue
        if char == "}":
            depth_brace -= 1
            if depth_brace < 0:
                raise ValueExpressionParseError("Unexpected '}' in adapter body", position, position + 1)
            position += 1
            continue
        if (
            char.isspace()
            and depth_paren == 0
            and depth_bracket == 0
            and depth_brace == 0
            and text.startswith("with{", position + 1)
        ):
            binding_start = position + 1
            binding_end = _find_balanced_brace_end(text, binding_start + 4)
            bindings = _parse_adapter_bindings(
                text[binding_start + 5 : binding_end - 1],
                start_offset=binding_start + 5,
                allow_boolean_composition=allow_boolean_composition,
            )
            return text[body_start:position].rstrip(), bindings, binding_end
        position += 1

    if quote is not None:
        raise ValueExpressionParseError("Unterminated string literal", len(text) - 1, len(text))
    if depth_paren != 0 or depth_bracket != 0 or depth_brace != 0:
        raise ValueExpressionParseError("Unbalanced adapter body structure", body_start, len(text))
    return text[body_start:].rstrip(), (), len(text)


def _find_balanced_brace_end(text: str, open_brace_index: int) -> int:
    if open_brace_index >= len(text) or text[open_brace_index] != "{":
        raise ValueExpressionParseError("Expected '{' to start outer adapter binding suffix", open_brace_index, open_brace_index + 1)
    depth = 1
    position = open_brace_index + 1
    quote: str | None = None
    escape = False
    while position < len(text):
        char = text[position]
        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            position += 1
            continue
        if char in {'"', "'"}:
            quote = char
            position += 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return position + 1
        position += 1
    raise ValueExpressionParseError("Expected '}' to close outer adapter binding suffix", open_brace_index, len(text))


def _parse_adapter_bindings(
    binding_text: str,
    *,
    start_offset: int,
    allow_boolean_composition: bool,
) -> tuple[AdapterBindingNode, ...]:
    if not binding_text.strip():
        return ()
    items = _split_top_level_items(binding_text)
    bindings: list[AdapterBindingNode] = []
    for item_text, relative_start in items:
        name, value_text, name_start, value_start = _split_binding_item(item_text, start_offset=start_offset + relative_start)
        parsed_value = parse_local_expression_tree(value_text, allow_boolean_composition=allow_boolean_composition)
        value_node = _shift_node_offsets(parsed_value.root, delta=value_start)
        bindings.append(AdapterBindingNode(start=name_start, end=value_node.end, name=name, value=value_node))
    return tuple(bindings)


def _split_top_level_items(text: str) -> tuple[tuple[str, int], ...]:
    items: list[tuple[str, int]] = []
    start = 0
    depth_paren = 0
    depth_bracket = 0
    quote: str | None = None
    escape = False
    for index, char in enumerate(text):
        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char == "(":
            depth_paren += 1
            continue
        if char == ")":
            depth_paren -= 1
            continue
        if char == "[":
            depth_bracket += 1
            continue
        if char == "]":
            depth_bracket -= 1
            continue
        if char == "," and depth_paren == 0 and depth_bracket == 0:
            items.append((text[start:index], start))
            start = index + 1
    items.append((text[start:], start))
    return tuple(items)


def _split_binding_item(item_text: str, *, start_offset: int) -> tuple[str, str, int, int]:
    colon_index = _find_top_level_separator(item_text, separator=":")
    if colon_index is None:
        raise ValueExpressionParseError("Expected ':' in outer adapter binding", start_offset, start_offset + len(item_text))
    raw_name = item_text[:colon_index].strip()
    if not raw_name or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", raw_name) is None:
        raise ValueExpressionParseError("Outer adapter binding names must be identifiers", start_offset, start_offset + max(colon_index, 1))
    raw_value = item_text[colon_index + 1 :].strip()
    if not raw_value:
        value_position = start_offset + colon_index + 1
        raise ValueExpressionParseError("Expected value in outer adapter binding", value_position, value_position + 1)
    name_start = start_offset + item_text.index(raw_name)
    suffix = item_text[colon_index + 1 :]
    value_start = start_offset + colon_index + 1 + len(suffix) - len(suffix.lstrip())
    return raw_name, raw_value, name_start, value_start


def _find_top_level_separator(text: str, *, separator: str) -> int | None:
    depth_paren = 0
    depth_bracket = 0
    quote: str | None = None
    escape = False
    for index, char in enumerate(text):
        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char == "(":
            depth_paren += 1
            continue
        if char == ")":
            depth_paren -= 1
            continue
        if char == "[":
            depth_bracket += 1
            continue
        if char == "]":
            depth_bracket -= 1
            continue
        if char == separator and depth_paren == 0 and depth_bracket == 0:
            return index
    return None


class _Parser:
    def __init__(self, text: str, *, allow_boolean_composition: bool) -> None:
        self._text = text
        self._tokens = _tokenize(text)
        self._index = 0
        self._allow_boolean_composition = allow_boolean_composition

    def parse(self) -> ValueExpressionNode:
        node = self._parse_or() if self._allow_boolean_composition else self._parse_pipeline()
        if self._peek().kind != "EOF":
            token = self._peek()
            raise ValueExpressionParseError("Unexpected trailing token", token.start, token.end)
        return node

    def _parse_or(self) -> ValueExpressionNode:
        return parse_boolean_or(parse_and=self._parse_and, match_keyword=self._match_keyword, make_binary=self._make_boolean_binary)

    def _parse_and(self) -> ValueExpressionNode:
        return parse_boolean_and(parse_not=self._parse_not, match_keyword=self._match_keyword, make_binary=self._make_boolean_binary)

    def _parse_not(self) -> ValueExpressionNode:
        return parse_boolean_not(
            match_not=lambda: self._match_keyword("not"),
            parse_not=self._parse_not,
            parse_fallback=self._parse_comparison,
            make_unary=self._make_boolean_unary,
        )

    def _parse_comparison(self) -> ValueExpressionNode:
        node = self._parse_pipeline()
        if self._match("EQEQ") is not None:
            right = self._parse_pipeline()
            return BinaryNode(start=node.start, end=right.end, operator="==", left=node, right=right)
        if self._match("NEQ") is not None:
            right = self._parse_pipeline()
            return BinaryNode(start=node.start, end=right.end, operator="!=", left=node, right=right)
        if self._peek_kind("IDENT", expected_text="not") and self._peek_kind("IDENT", offset=1, expected_text="in"):
            self._advance()
            self._advance()
            right = self._parse_pipeline()
            return BinaryNode(start=node.start, end=right.end, operator="not in", left=node, right=right)
        if self._match_keyword("in") is not None:
            right = self._parse_pipeline()
            return BinaryNode(start=node.start, end=right.end, operator="in", left=node, right=right)
        return node

    def _parse_pipeline(self) -> ValueExpressionNode:
        source = self._parse_primary()
        filters: list[ValueExpressionNode] = []
        while self._match("PIPE") is not None:
            token = self._peek()
            if token.kind == "IDENT":
                adapter_node = _try_parse_adapter_invocation_at(
                    self._text,
                    start=token.start,
                    allow_boolean_composition=self._allow_boolean_composition,
                    stop_chars=",)]|",
                    allow_empty_body=True,
                )
                if adapter_node is not None:
                    self._advance_to_position(adapter_node.end)
                    filters.append(adapter_node)
                    continue
            name_token = self._consume("IDENT", "Expected filter name after '|'")
            arguments: list[ValueExpressionNode] = []
            end = name_token.end
            if self._match("LPAREN") is not None:
                if name_token.text == "only":
                    if self._peek().kind != "RPAREN":
                        arguments.append(self._parse_only_predicate())
                    end = self._consume("RPAREN", "Expected ')' after filter arguments").end
                    filters.append(FilterApplicationNode(start=name_token.start, end=end, name=name_token.text, arguments=tuple(arguments)))
                    continue
                if self._peek().kind != "RPAREN":
                    while True:
                        arguments.append(self._parse_pipeline())
                        if self._match("COMMA") is None:
                            break
                end = self._consume("RPAREN", "Expected ')' after filter arguments").end
            filters.append(FilterApplicationNode(start=name_token.start, end=end, name=name_token.text, arguments=tuple(arguments)))
        if not filters:
            return source
        return PipelineNode(start=source.start, end=filters[-1].end, source=source, filters=tuple(filters))

    def _parse_only_predicate(self) -> OnlyPredicateNode:
        path_start = self._peek().start
        path_parts: list[str] = []
        token = self._consume("IDENT", "Filter 'only' requires a field path before '=' or '!='")
        path_parts.append(token.text)
        path_end = token.end
        while True:
            if self._match("DOT") is not None:
                field = self._consume("IDENT", "Filter 'only' path expected an identifier after '.'")
                path_parts.extend((".", field.text))
                path_end = field.end
                continue
            if self._match("LBRACKET") is not None:
                index = self._consume("NUMBER", "Filter 'only' path indexes must use non-negative integers")
                if "." in index.text or index.text.startswith("-"):
                    raise ValueExpressionParseError("Filter 'only' path indexes must use non-negative integers", index.start, index.end)
                closing = self._consume("RBRACKET", "Filter 'only' path index is missing a closing bracket")
                path_parts.extend(("[", index.text, "]"))
                path_end = closing.end
                continue
            break
        operator_token = self._peek()
        if operator_token.kind == "EQUAL":
            self._advance()
            operator: Literal["=", "!="] = "="
        elif operator_token.kind == "NEQ":
            self._advance()
            operator = "!="
        else:
            raise ValueExpressionParseError("Filter 'only' requires one field=value or field!=value predicate", operator_token.start, operator_token.end)
        expected = self._parse_or() if self._allow_boolean_composition else self._parse_pipeline()
        if self._peek().kind == "COMMA":
            raise ValueExpressionParseError("Filter 'only' accepts exactly one field=value or field!=value predicate", self._peek().start, self._peek().end)
        return OnlyPredicateNode(
            start=path_start,
            end=expected.end,
            path="".join(path_parts),
            operator=operator,
            expected=expected,
        )

    def _parse_primary(self) -> ValueExpressionNode:
        token = self._peek()
        if token.kind == "LPAREN":
            self._advance()
            node = self._parse_or() if self._allow_boolean_composition else self._parse_pipeline()
            end = self._consume("RPAREN", "Expected ')' to close grouped expression")
            return _with_grouped_end(node, end.end)
        if token.kind == "LBRACKET":
            return self._parse_list()
        if token.kind == "LBRACE":
            return self._parse_object()
        if token.kind == "STRING":
            self._advance()
            return LiteralNode(start=token.start, end=token.end, value=_decode_string(token.text, token.start))
        if token.kind == "NUMBER":
            self._advance()
            return LiteralNode(start=token.start, end=token.end, value=_decode_number(token.text))
        if token.kind != "IDENT":
            raise ValueExpressionParseError("Expected local-expression term", token.start, token.end)
        adapter_node = _try_parse_adapter_invocation_at(
            self._text,
            start=token.start,
            allow_boolean_composition=self._allow_boolean_composition,
            stop_chars=",)]",
        )
        if adapter_node is not None:
            self._advance_to_position(adapter_node.end)
            return adapter_node
        if token.text in {"true", "false", "null"}:
            self._advance()
            value = {"true": True, "false": False, "null": None}[token.text]
            return LiteralNode(start=token.start, end=token.end, value=value)
        if self._peek_kind("IDENT", expected_text="state"):
            return self._parse_state_reference()
        if self._peek_kind("IDENT", expected_text="step"):
            return self._parse_step_reference()
        if self._peek_kind("IDENT") and self._peek_kind("LPAREN", offset=1):
            return self._parse_builtin_call()
        return self._parse_reference_or_call()

    def _parse_builtin_call(self) -> BuiltinCallNode | CallNode:
        name_token = self._consume("IDENT", "Expected built-in name")
        self._consume("LPAREN", "Expected '(' after built-in name")
        if name_token.text in VALUE_EXPRESSION_BUILTINS:
            arguments: list[ValueExpressionNode] = []
            if self._peek().kind != "RPAREN":
                while True:
                    arguments.append(self._parse_or() if self._allow_boolean_composition else self._parse_pipeline())
                    if self._match("COMMA") is None:
                        break
            end = self._consume("RPAREN", "Expected ')' after built-in arguments").end
            return BuiltinCallNode(start=name_token.start, end=end, name=name_token.text, arguments=tuple(arguments))

        arguments = self._parse_named_call_arguments()
        closing = self._consume("RPAREN", "Expected ')' after call arguments")
        fields = self._parse_field_suffixes()
        end = fields[1] if fields is not None else closing.end
        return CallNode(
            start=name_token.start,
            end=end,
            target=ReferenceNode(start=name_token.start, end=name_token.end, parts=(name_token.text,)),
            arguments=arguments,
            fields=fields[0] if fields is not None else (),
        )

    def _parse_dotted_reference(self) -> ReferenceNode:
        start_token = self._consume("IDENT", "Expected identifier")
        parts = [start_token.text]
        end = start_token.end
        while self._match("DOT") is not None:
            next_token = self._consume("IDENT", "Expected identifier after '.'")
            parts.append(next_token.text)
            end = next_token.end
        return ReferenceNode(start=start_token.start, end=end, parts=tuple(parts))

    def _parse_reference_or_call(self) -> ReferenceNode | CallNode:
        reference = self._parse_dotted_reference()
        if self._match("LPAREN") is None:
            return reference
        arguments = self._parse_named_call_arguments()
        closing = self._consume("RPAREN", "Expected ')' after call arguments")
        fields = self._parse_field_suffixes()
        end = fields[1] if fields is not None else closing.end
        return CallNode(start=reference.start, end=end, target=reference, arguments=arguments, fields=fields[0] if fields is not None else ())

    def _parse_named_call_arguments(self) -> tuple[CallArgumentNode, ...]:
        arguments: list[CallArgumentNode] = []
        if self._peek().kind == "RPAREN":
            return ()
        while True:
            name_token = self._consume("IDENT", "Expected named argument")
            self._consume("EQUAL", "Expected '=' after argument name")
            value = self._parse_or() if self._allow_boolean_composition else self._parse_pipeline()
            arguments.append(CallArgumentNode(start=name_token.start, end=value.end, name=name_token.text, value=value))
            if self._match("COMMA") is None:
                break
        return tuple(arguments)

    def _parse_field_suffixes(self) -> tuple[tuple[str, ...], int] | None:
        fields: list[str] = []
        end: int | None = None
        while self._match("DOT") is not None:
            field_token = self._consume("IDENT", "Expected field name after '.'")
            fields.append(field_token.text)
            end = field_token.end
        if not fields or end is None:
            return None
        return tuple(fields), end

    def _parse_list(self) -> ListNode:
        start = self._consume("LBRACKET", "Expected '[' to start list literal").start
        items: list[ValueExpressionNode] = []
        if self._peek().kind != "RBRACKET":
            while True:
                items.append(self._parse_or() if self._allow_boolean_composition else self._parse_pipeline())
                if self._match("COMMA") is None:
                    break
        end = self._consume("RBRACKET", "Expected ']' to close list literal").end
        return ListNode(start=start, end=end, items=tuple(items))

    def _parse_object(self) -> ObjectNode:
        start = self._consume("LBRACE", "Expected '{' to start object literal").start
        entries: list[ObjectEntryNode] = []
        if self._peek().kind != "RBRACE":
            while True:
                key_token = self._peek()
                if key_token.kind == "IDENT":
                    self._advance()
                    key = key_token.text
                elif key_token.kind == "STRING":
                    self._advance()
                    key = _decode_string(key_token.text, key_token.start)
                else:
                    raise ValueExpressionParseError("Expected object key", key_token.start, key_token.end)
                self._consume("COLON", "Expected ':' after object key")
                value = self._parse_or() if self._allow_boolean_composition else self._parse_pipeline()
                entries.append(ObjectEntryNode(start=key_token.start, end=value.end, key=key, value=value))
                if self._match("COMMA") is None:
                    break
        end = self._consume("RBRACE", "Expected '}' to close object literal").end
        return ObjectNode(start=start, end=end, entries=tuple(entries))

    def _parse_state_reference(self) -> StateReferenceNode:
        start = self._consume("IDENT", "Expected 'state'")
        self._consume("DOT", "Expected '.' after 'state'")
        state_role = self._consume("IDENT", "Expected state role")
        self._consume("LBRACKET", "Expected '[' after state role")
        key_reference = self._parse_dotted_reference()
        if key_reference.parts[0] != "inputs" or len(key_reference.parts) < 2:
            raise ValueExpressionParseError(
                "State path key reference must use dotted form such as 'inputs.task_key'",
                key_reference.start,
                key_reference.end,
            )
        self._consume("RBRACKET", "Expected ']' after state key reference")
        fields: list[str] = []
        end = state_role.end
        while self._match("DOT") is not None:
            field_token = self._consume("IDENT", "Expected field name after '.'")
            fields.append(field_token.text)
            end = field_token.end
        if fields:
            end = end
        else:
            end = self._previous().end if self._previous().kind == "RBRACKET" else state_role.end
        return StateReferenceNode(
            start=start.start,
            end=end,
            state_role=state_role.text,
            key_reference=key_reference.parts,
            fields=tuple(fields),
        )

    def _parse_step_reference(self) -> StepReferenceNode:
        start = self._consume("IDENT", "Expected 'step'")
        self._consume("DOT", "Expected '.' after 'step'")
        register = self._consume("IDENT", "Expected registered step identifier")
        self._consume("DOT", "Expected '.' after registered step identifier")
        field = self._consume("IDENT", "Expected registered step field")
        fields = [field.text]
        end = field.end
        while self._match("DOT") is not None:
            next_field = self._consume("IDENT", "Expected registered step field after '.'")
            fields.append(next_field.text)
            end = next_field.end
        return StepReferenceNode(start=start.start, end=end, register=register.text, fields=tuple(fields))

    def _peek(self) -> _Token:
        return self._tokens[self._index]

    def _peek_kind(self, kind: str, *, offset: int = 0, expected_text: str | None = None) -> bool:
        token = self._tokens[min(self._index + offset, len(self._tokens) - 1)]
        if token.kind != kind:
            return False
        if expected_text is not None and token.text != expected_text:
            return False
        return True

    def _previous(self) -> _Token:
        return self._tokens[self._index - 1]

    def _advance(self) -> _Token:
        token = self._tokens[self._index]
        self._index += 1
        return token

    def _consume(self, kind: str, message: str) -> _Token:
        token = self._peek()
        if token.kind != kind:
            raise ValueExpressionParseError(message, token.start, token.end)
        return self._advance()

    def _advance_to_position(self, end: int) -> None:
        while self._peek().kind != "EOF" and self._peek().start < end:
            self._advance()

    def _match(self, kind: str) -> _Token | None:
        if self._peek().kind != kind:
            return None
        return self._advance()

    def _match_keyword(self, keyword: str) -> _Token | None:
        token = self._peek()
        if token.kind != "IDENT" or token.text != keyword:
            return None
        return self._advance()

    def _make_boolean_binary(self, operator: str, left: ValueExpressionNode, right: ValueExpressionNode) -> BinaryNode:
        return BinaryNode(start=left.start, end=right.end, operator=operator, left=left, right=right)

    def _make_boolean_unary(self, operator: str, token: _Token, operand: ValueExpressionNode) -> UnaryNode:
        return UnaryNode(start=token.start, end=operand.end, operator=operator, operand=operand)


class _SemanticValidator:
    def __init__(self, parsed: ParsedValueExpression, *, workflow: Workflow | None = None, context: LocalExpressionContext | None = None) -> None:
        self._parsed = parsed
        self._workflow = workflow
        self._context = context
        self._errors: list[ValueExpressionValidationError] = []

    def validate(self) -> list[ValueExpressionValidationError]:
        self._visit(self._parsed.root)
        return self._errors

    def _visit(self, node: ValueExpressionNode) -> None:
        if isinstance(node, LiteralNode):
            return
        if isinstance(node, ReferenceNode):
            self._validate_reference(node)
            return
        if isinstance(node, (StateReferenceNode, StepReferenceNode)):
            return
        if isinstance(node, ListNode):
            for item in node.items:
                self._visit(item)
            return
        if isinstance(node, ObjectEntryNode):
            self._visit(node.value)
            return
        if isinstance(node, ObjectNode):
            for entry in node.entries:
                self._visit(entry)
            return
        if isinstance(node, CallArgumentNode):
            self._visit(node.value)
            return
        if isinstance(node, CallNode):
            self._validate_call(node)
            return
        if isinstance(node, FilterApplicationNode):
            self._validate_filter(node)
            for argument in node.arguments:
                self._visit(argument)
            return
        if isinstance(node, OnlyPredicateNode):
            self._visit(node.expected)
            return
        if isinstance(node, PipelineNode):
            self._visit(node.source)
            for item in node.filters:
                self._visit(item)
            return
        if isinstance(node, BuiltinCallNode):
            self._validate_builtin(node)
            for argument in node.arguments:
                self._visit(argument)
            return
        if isinstance(node, UnaryNode):
            self._visit(node.operand)
            return
        if isinstance(node, BinaryNode):
            self._visit(node.left)
            self._visit(node.right)
            return
        if isinstance(node, AdapterBindingNode):
            self._visit(node.value)
            return
        if isinstance(node, AdapterInvocationNode):
            for binding in node.bindings:
                self._visit(binding)
            return

    def _validate_call(self, node: CallNode) -> None:
        if node.target.parts[0] == "inputs":
            self._error(
                "validation.workflow.value_expr.inputs_call",
                "Workflow input references are values and must not be called like probes",
                node.target,
            )
        elif len(node.target.parts) < 2:
            self._error(
                "validation.workflow.value_expr.call_target",
                "Read-only probe calls must target a dotted public reference such as 'gh.issue'",
                node.target,
            )

        seen_names: set[str] = set()
        for argument in node.arguments:
            if argument.name in seen_names:
                self._error(
                    "validation.workflow.value_expr.duplicate_argument",
                    f"Duplicate local-expression argument '{argument.name}'",
                    argument,
                )
            else:
                seen_names.add(argument.name)
            self._visit(argument)

    def _validate_reference(self, node: ReferenceNode) -> None:
        if node.parts[0] == "inputs" and len(node.parts) < 2:
            self._error(
                "validation.workflow.value_expr.input_ref",
                "Workflow input references must use dotted form such as 'inputs.issue'",
                node,
            )
            return
        if node.parts[0] == "args" and len(node.parts) < 2:
            self._error(
                "validation.workflow.value_expr.arg_ref",
                "Fragment argument references must use dotted form such as 'args.name'",
                node,
            )

    def _validate_builtin(self, node: BuiltinCallNode) -> None:
        if node.name not in {"is_missing", "is_present"}:
            return
        if len(node.arguments) != 1:
            self._error(
                "validation.workflow.value_expr.presence_check_arity",
                f"Built-in value expression '{node.name}' requires exactly one argument",
                node,
            )
            return
        argument = node.arguments[0]
        if not _is_presence_check_argument(self._expand_presence_check_argument(argument)):
            self._error(
                "validation.workflow.value_expr.presence_check_argument",
                f"Built-in value expression '{node.name}' requires a lookup-style reference or read-only adapter invocation argument",
                argument,
            )

    def _expand_presence_check_argument(self, node: ValueExpressionNode) -> ValueExpressionNode:
        if self._workflow is None or self._context is None or not isinstance(node, ReferenceNode):
            return node
        from ordo.runtime.local_expressions import LOCAL_EXPRESSION_PARSE_ERRORS, resolve_workflow_let_reference_node

        try:
            expanded = resolve_workflow_let_reference_node(node, self._workflow, context=self._context)
        except LOCAL_EXPRESSION_PARSE_ERRORS:
            return node
        return node if expanded is None else expanded

    def _validate_filter(self, node: FilterApplicationNode) -> None:
        spec = VALUE_EXPRESSION_FILTERS.get(node.name)
        if spec is None:
            self._error(
                "validation.workflow.value_expr.filter_unknown",
                f"Unknown local-expression filter '{node.name}'",
                node,
            )
            return
        if len(node.arguments) != spec.argument_count:
            self._error(
                "validation.workflow.value_expr.filter_arity",
                f"Filter '{node.name}' requires exactly {spec.argument_count} argument(s)",
                node,
            )
            return
        if node.name != "field":
            return
        argument = node.arguments[0]
        if isinstance(argument, LiteralNode):
            if not isinstance(argument.value, str):
                self._error(
                    "validation.workflow.value_expr.field_path_type",
                    "Filter 'field' requires a string path argument",
                    argument,
                )
                return
            try:
                _parse_field_path(argument.value)
            except _FieldPathSyntaxError as exc:
                self._error(
                    "validation.workflow.value_expr.field_path_invalid",
                    exc.message,
                    argument,
                )

    def _error(self, code: str, message: str, node: ValueExpressionNode) -> None:
        self._errors.append(ValueExpressionValidationError(code=code, message=message, start=node.start, end=node.end))


class _ConditionEvaluator:
    def __init__(
        self,
        parsed: ParsedValueExpression,
        workflow: Workflow,
        *,
        context,
        observation_session: ReadOnlyObservationSession,
        step_results: dict[str, OperationResult | JSONObject],
    ) -> None:
        self._parsed = parsed
        self._workflow = workflow
        self._context = context
        self._observation_session = observation_session
        self._step_results = step_results
        self._diagnostics: list[Diagnostic] = []
        self._trace: list[ConditionTraceEntry] = []

    def evaluate(self) -> ConditionEvaluationResult:
        status, value = self._evaluate(self._parsed.root)
        return ConditionEvaluationResult(
            status=status,
            value=value,
            diagnostics=tuple(self._diagnostics),
            trace=tuple(self._trace),
            cache_entries=self._observation_session.cache_entries,
        )

    def _evaluate(self, node: ValueExpressionNode) -> tuple[Literal["ok", "probe_failed"], JSONValue | None]:
        if isinstance(node, LiteralNode):
            value = node.value
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="literal", status="ok", value=value))
            return "ok", value
        if isinstance(node, ListNode):
            values: list[JSONValue] = []
            for item in node.items:
                status, value = self._evaluate(item)
                if status != "ok":
                    return status, None
                values.append(value)
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="list", status="ok", value=values))
            return "ok", values
        if isinstance(node, ObjectEntryNode):
            return self._evaluate(node.value)
        if isinstance(node, ObjectNode):
            values: dict[str, JSONValue] = {}
            for entry in node.entries:
                status, value = self._evaluate(entry.value)
                if status != "ok":
                    return status, None
                values[entry.key] = value
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="object", status="ok", value=values))
            return "ok", values
        if isinstance(node, ReferenceNode):
            from ordo.runtime.local_expression_contexts import LocalExpressionContext
            from ordo.runtime.local_expressions import LOCAL_EXPRESSION_PARSE_ERRORS, resolve_workflow_let_reference_node

            try:
                expanded = resolve_workflow_let_reference_node(node, self._workflow, context=LocalExpressionContext.GUARD)
            except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
                self._diagnostics.append(
                    Diagnostic(
                        code="runtime.local_expression.let_binding_invalid",
                        level="error",
                        message=f"Workflow let binding '{node.parts[0]}' is not valid in the guard local-expression context",
                        path=(),
                        details={
                            "expression": self._parsed.source,
                            "binding_name": node.parts[0],
                            "binding_path": ["let", node.parts[0]],
                            "position": exc.position,
                            "end": exc.end if exc.end is not None else exc.position,
                            "parse_message": exc.message,
                        },
                    )
                )
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="let", status="probe_failed", value=None))
                return "probe_failed", None
            if expanded is not None:
                return self._evaluate(expanded)
            if node.parts[0] == "inputs":
                try:
                    value = _resolve_input_reference(node.parts, workflow=self._workflow)
                except ValueExpressionEvaluationError as exc:
                    self._diagnostics.append(exc.to_diagnostic())
                    self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="input", status="probe_failed", value=None))
                    return "probe_failed", None
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="input", status="ok", value=value))
                return "ok", value
            if node.parts[0] == "args":
                try:
                    value = _resolve_args_reference(node.parts, workflow=self._workflow)
                except ValueExpressionEvaluationError as exc:
                    self._diagnostics.append(exc.to_diagnostic())
                    self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="arg", status="probe_failed", value=None))
                    return "probe_failed", None
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="arg", status="ok", value=value))
                return "ok", value
            if node.parts[0] == "item":
                try:
                    value = _resolve_iteration_item_reference(node.parts, workflow=self._workflow)
                except ValueExpressionEvaluationError as exc:
                    self._diagnostics.append(exc.to_diagnostic())
                    self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="item", status="probe_failed", value=None))
                    return "probe_failed", None
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="item", status="ok", value=value))
                return "ok", value
            return self._observe_reference(node)
        if isinstance(node, StateReferenceNode):
            try:
                value = _resolve_state_reference(node, parsed=self._parsed, workflow=self._workflow)
            except ValueExpressionEvaluationError as exc:
                self._diagnostics.append(exc.to_diagnostic())
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="state", status="probe_failed", value=None))
                return "probe_failed", None
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="state", status="ok", value=value))
            return "ok", value
        if isinstance(node, StepReferenceNode):
            try:
                value = _resolve_step_reference(node, parsed=self._parsed, step_results=self._step_results)
            except ValueExpressionEvaluationError as exc:
                self._diagnostics.append(exc.to_diagnostic())
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="step", status="probe_failed", value=None))
                return "probe_failed", None
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="step", status="ok", value=value))
            return "ok", value
        if isinstance(node, CallNode):
            return self._observe_call(node)
        if isinstance(node, BuiltinCallNode):
            from ordo.runtime.local_expression_contexts import LocalExpressionContext

            try:
                value = _evaluate_presence_builtin(
                    node,
                    parsed=self._parsed,
                    workflow=self._workflow,
                    context=self._context,
                    step_results=self._step_results,
                    observation_session=self._observation_session,
                )
            except ValueExpressionEvaluationError as exc:
                self._diagnostics.append(exc.to_diagnostic())
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="builtin", status="probe_failed", value=None))
                return "probe_failed", None
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="builtin", status="ok", value=value))
            return "ok", value
        if isinstance(node, (PipelineNode, AdapterInvocationNode)):
            from ordo.runtime.local_expression_contexts import LocalExpressionContext

            try:
                value = _evaluate_node(
                    node,
                    parsed=self._parsed,
                    workflow=self._workflow,
                    context=self._context,
                    step_results=self._step_results,
                    observation_session=self._observation_session,
                )
            except ValueExpressionEvaluationError as exc:
                self._diagnostics.append(exc.to_diagnostic())
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="value", status="probe_failed", value=None))
                return "probe_failed", None
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="value", status="ok", value=value))
            return "ok", value
        if isinstance(node, UnaryNode):
            status, value = self._evaluate(node.operand)
            if status != "ok":
                return status, None
            result = not bool(value)
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="unary", status="ok", value=result, operator=node.operator))
            return "ok", result
        if isinstance(node, BinaryNode):
            return self._evaluate_binary(node)
        raise ValueExpressionEvaluationError(
            code="runtime.local_expression.condition_node_unsupported",
            message=f"Condition evaluation does not support node '{type(node).__name__}'",
            details={"expression": self._parsed.source, "node_type": type(node).__name__},
        )

    def _observe_reference(self, node: ReferenceNode) -> tuple[Literal["ok", "probe_failed"], JSONValue | None]:
        request = ConditionObservationRequest(expression_text=self._expr(node), target=node.parts)
        result = self._observe_cached(request)
        self._trace.append(
            ConditionTraceEntry(
                expr=request.expression_text,
                kind="probe",
                status=result.status,
                value=result.value,
                reference=result.reference,
            )
        )
        return result.status, result.value

    def _observe_call(self, node: CallNode) -> tuple[Literal["ok", "probe_failed"], JSONValue | None]:
        arguments: list[tuple[str, JSONValue]] = []
        for argument in node.arguments:
            status, value = self._evaluate(argument.value)
            if status != "ok":
                return status, None
            arguments.append((argument.name, value))
        request = ConditionObservationRequest(
            expression_text=self._expr(node),
            target=node.target.parts,
            fields=node.fields,
            arguments=tuple(arguments),
        )
        result = self._observe_cached(request)
        self._trace.append(
            ConditionTraceEntry(
                expr=request.expression_text,
                kind="probe",
                status=result.status,
                value=result.value,
                reference=result.reference,
            )
        )
        return result.status, result.value

    def _observe_cached(self, request: ConditionObservationRequest) -> ConditionObservationResult:
        outcome = self._observation_session.observe(request)
        if not outcome.cached:
            self._diagnostics.extend(outcome.result.diagnostics)
        return outcome.result

    def _evaluate_binary(self, node: BinaryNode) -> tuple[Literal["ok", "probe_failed"], JSONValue | None]:
        if node.operator == "and":
            left_status, left_value = self._evaluate(node.left)
            if left_status != "ok":
                return left_status, None
            if not bool(left_value):
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="binary", status="ok", value=False, operator=node.operator))
                return "ok", False
            right_status, right_value = self._evaluate(node.right)
            if right_status != "ok":
                return right_status, None
            result = bool(right_value)
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="binary", status="ok", value=result, operator=node.operator))
            return "ok", result
        if node.operator == "or":
            left_status, left_value = self._evaluate(node.left)
            if left_status != "ok":
                return left_status, None
            if bool(left_value):
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="binary", status="ok", value=True, operator=node.operator))
                return "ok", True
            right_status, right_value = self._evaluate(node.right)
            if right_status != "ok":
                return right_status, None
            result = bool(right_value)
            self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="binary", status="ok", value=result, operator=node.operator))
            return "ok", result
        left_status, left_value = self._evaluate(node.left)
        if left_status != "ok":
            return left_status, None
        right_status, right_value = self._evaluate(node.right)
        if right_status != "ok":
            return right_status, None
        result: JSONValue
        if node.operator == "==":
            result = left_value == right_value
        elif node.operator == "!=":
            result = left_value != right_value
        elif node.operator == "in":
            result = left_value in right_value  # type: ignore[operator]
        elif node.operator == "not in":
            result = left_value not in right_value  # type: ignore[operator]
        else:
            raise ValueExpressionEvaluationError(
                code="runtime.local_expression.operator_unsupported",
                message=f"Unsupported condition operator '{node.operator}'",
                details={"expression": self._parsed.source, "operator": node.operator},
            )
        self._trace.append(
            ConditionTraceEntry(
                expr=self._expr(node),
                kind="binary",
                status="ok",
                value=result,
                operator=node.operator,
                left=left_value,
                right=right_value,
            )
        )
        return "ok", result

    def _expr(self, node: ValueExpressionNode) -> str:
        return render_expression_text(node, source=self._parsed.source)


def _tokenize(text: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    length = len(text)
    position = 0

    while position < length:
        char = text[position]
        if char.isspace():
            position += 1
            continue
        if char == ".":
            tokens.append(_Token("DOT", char, position, position + 1))
            position += 1
            continue
        if char == "{":
            tokens.append(_Token("LBRACE", char, position, position + 1))
            position += 1
            continue
        if char == "}":
            tokens.append(_Token("RBRACE", char, position, position + 1))
            position += 1
            continue
        if char == "[":
            tokens.append(_Token("LBRACKET", char, position, position + 1))
            position += 1
            continue
        if char == "]":
            tokens.append(_Token("RBRACKET", char, position, position + 1))
            position += 1
            continue
        if char == "|":
            tokens.append(_Token("PIPE", char, position, position + 1))
            position += 1
            continue
        if char == "(":
            tokens.append(_Token("LPAREN", char, position, position + 1))
            position += 1
            continue
        if char == ")":
            tokens.append(_Token("RPAREN", char, position, position + 1))
            position += 1
            continue
        if char == ",":
            tokens.append(_Token("COMMA", char, position, position + 1))
            position += 1
            continue
        if char == ":":
            tokens.append(_Token("COLON", char, position, position + 1))
            position += 1
            continue
        if char == "-" and position + 1 < length and text[position + 1] == ">":
            tokens.append(_Token("ARROW", "->", position, position + 2))
            position += 2
            continue
        if char == "=" and position + 1 < length and text[position + 1] == "=":
            tokens.append(_Token("EQEQ", "==", position, position + 2))
            position += 2
            continue
        if char == "!" and position + 1 < length and text[position + 1] == "=":
            tokens.append(_Token("NEQ", "!=", position, position + 2))
            position += 2
            continue
        if char == "=":
            tokens.append(_Token("EQUAL", char, position, position + 1))
            position += 1
            continue
        if char in {'"', "'"}:
            start = position
            position = _consume_string(text, position)
            tokens.append(_Token("STRING", text[start:position], start, position))
            continue
        if char.isdigit() or (char == "-" and position + 1 < length and text[position + 1].isdigit()):
            start = position
            if char == "-":
                position += 1
            position += 1
            while position < length and text[position].isdigit():
                position += 1
            if position < length and text[position] == ".":
                position += 1
                if position >= length or not text[position].isdigit():
                    raise ValueExpressionParseError("Invalid number literal", start, position)
                while position < length and text[position].isdigit():
                    position += 1
            tokens.append(_Token("NUMBER", text[start:position], start, position))
            continue
        if char.isalpha() or char == "_":
            start = position
            position += 1
            while position < length and (
                text[position].isalnum()
                or text[position] == "_"
                or (text[position] == "-" and (position + 1 >= length or text[position + 1] != ">"))
            ):
                position += 1
            tokens.append(_Token("IDENT", text[start:position], start, position))
            continue
        raise ValueExpressionParseError(f"Unexpected character '{char}'", position, position + 1)

    tokens.append(_Token("EOF", "", length, length))
    return tuple(tokens)


def _with_grouped_end(node: ValueExpressionNode, end: int) -> ValueExpressionNode:
    if isinstance(node, LiteralNode):
        return LiteralNode(start=node.start, end=end, value=node.value)
    if isinstance(node, ReferenceNode):
        return ReferenceNode(start=node.start, end=end, parts=node.parts)
    if isinstance(node, StateReferenceNode):
        return StateReferenceNode(start=node.start, end=end, state_role=node.state_role, key_reference=node.key_reference, fields=node.fields)
    if isinstance(node, StepReferenceNode):
        return StepReferenceNode(start=node.start, end=end, register=node.register, fields=node.fields)
    if isinstance(node, ListNode):
        return ListNode(start=node.start, end=end, items=node.items)
    if isinstance(node, ObjectEntryNode):
        return ObjectEntryNode(start=node.start, end=end, key=node.key, value=node.value)
    if isinstance(node, ObjectNode):
        return ObjectNode(start=node.start, end=end, entries=node.entries)
    if isinstance(node, CallArgumentNode):
        return CallArgumentNode(start=node.start, end=end, name=node.name, value=node.value)
    if isinstance(node, CallNode):
        return CallNode(start=node.start, end=end, target=node.target, arguments=node.arguments, fields=node.fields)
    if isinstance(node, PipelineNode):
        return PipelineNode(start=node.start, end=end, source=node.source, filters=node.filters)
    if isinstance(node, OnlyPredicateNode):
        return OnlyPredicateNode(start=node.start, end=end, path=node.path, operator=node.operator, expected=node.expected)
    if isinstance(node, BuiltinCallNode):
        return BuiltinCallNode(start=node.start, end=end, name=node.name, arguments=node.arguments)
    if isinstance(node, UnaryNode):
        return UnaryNode(start=node.start, end=end, operator=node.operator, operand=node.operand)
    if isinstance(node, BinaryNode):
        return BinaryNode(start=node.start, end=end, operator=node.operator, left=node.left, right=node.right)
    if isinstance(node, AdapterBindingNode):
        return AdapterBindingNode(start=node.start, end=end, name=node.name, value=node.value)
    if isinstance(node, AdapterInvocationNode):
        return AdapterInvocationNode(start=node.start, end=end, family=node.family, body=node.body, bindings=node.bindings)
    return node


def _shift_node_offsets(node: ValueExpressionNode, *, delta: int) -> ValueExpressionNode:
    if isinstance(node, LiteralNode):
        return LiteralNode(start=node.start + delta, end=node.end + delta, value=node.value)
    if isinstance(node, ReferenceNode):
        return ReferenceNode(start=node.start + delta, end=node.end + delta, parts=node.parts)
    if isinstance(node, StateReferenceNode):
        return StateReferenceNode(
            start=node.start + delta,
            end=node.end + delta,
            state_role=node.state_role,
            key_reference=node.key_reference,
            fields=node.fields,
        )
    if isinstance(node, StepReferenceNode):
        return StepReferenceNode(start=node.start + delta, end=node.end + delta, register=node.register, fields=node.fields)
    if isinstance(node, ListNode):
        return ListNode(start=node.start + delta, end=node.end + delta, items=tuple(_shift_node_offsets(item, delta=delta) for item in node.items))
    if isinstance(node, ObjectEntryNode):
        return ObjectEntryNode(start=node.start + delta, end=node.end + delta, key=node.key, value=_shift_node_offsets(node.value, delta=delta))
    if isinstance(node, ObjectNode):
        return ObjectNode(start=node.start + delta, end=node.end + delta, entries=tuple(_shift_node_offsets(entry, delta=delta) for entry in node.entries))
    if isinstance(node, CallArgumentNode):
        return CallArgumentNode(start=node.start + delta, end=node.end + delta, name=node.name, value=_shift_node_offsets(node.value, delta=delta))
    if isinstance(node, CallNode):
        return CallNode(
            start=node.start + delta,
            end=node.end + delta,
            target=_shift_node_offsets(node.target, delta=delta),
            arguments=tuple(_shift_node_offsets(argument, delta=delta) for argument in node.arguments),
            fields=node.fields,
        )
    if isinstance(node, FilterApplicationNode):
        return FilterApplicationNode(
            start=node.start + delta,
            end=node.end + delta,
            name=node.name,
            arguments=tuple(_shift_node_offsets(argument, delta=delta) for argument in node.arguments),
        )
    if isinstance(node, OnlyPredicateNode):
        return OnlyPredicateNode(
            start=node.start + delta,
            end=node.end + delta,
            path=node.path,
            operator=node.operator,
            expected=_shift_node_offsets(node.expected, delta=delta),
        )
    if isinstance(node, PipelineNode):
        return PipelineNode(
            start=node.start + delta,
            end=node.end + delta,
            source=_shift_node_offsets(node.source, delta=delta),
            filters=tuple(_shift_node_offsets(item, delta=delta) for item in node.filters),
        )
    if isinstance(node, BuiltinCallNode):
        return BuiltinCallNode(
            start=node.start + delta,
            end=node.end + delta,
            name=node.name,
            arguments=tuple(_shift_node_offsets(argument, delta=delta) for argument in node.arguments),
        )
    if isinstance(node, UnaryNode):
        return UnaryNode(start=node.start + delta, end=node.end + delta, operator=node.operator, operand=_shift_node_offsets(node.operand, delta=delta))
    if isinstance(node, BinaryNode):
        return BinaryNode(
            start=node.start + delta,
            end=node.end + delta,
            operator=node.operator,
            left=_shift_node_offsets(node.left, delta=delta),
            right=_shift_node_offsets(node.right, delta=delta),
        )
    if isinstance(node, AdapterBindingNode):
        return AdapterBindingNode(start=node.start + delta, end=node.end + delta, name=node.name, value=_shift_node_offsets(node.value, delta=delta))
    if isinstance(node, AdapterInvocationNode):
        return AdapterInvocationNode(
            start=node.start + delta,
            end=node.end + delta,
            family=node.family,
            body=node.body,
            bindings=tuple(_shift_node_offsets(binding, delta=delta) for binding in node.bindings),
        )
    return node


def _evaluate_node(
    node: ValueExpressionNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, ReferenceNode):
        from ordo.runtime.local_expression_contexts import LocalExpressionContext
        from ordo.runtime.local_expressions import LOCAL_EXPRESSION_PARSE_ERRORS, resolve_workflow_let_reference_node

        try:
            expanded = resolve_workflow_let_reference_node(node, workflow, context=context)
        except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
            raise ValueExpressionEvaluationError(
                code="runtime.local_expression.let_binding_invalid",
                message=f"Workflow let binding '{node.parts[0]}' is not valid in the {context.value} local-expression context",
                details={
                    "expression": parsed.source,
                    "binding_name": node.parts[0],
                    "binding_path": ["let", node.parts[0]],
                    "context": context.value,
                    "position": exc.position,
                    "end": exc.end if exc.end is not None else exc.position,
                    "parse_message": exc.message,
                },
            ) from exc
        if expanded is not None:
            return _evaluate_node(
                expanded,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
        if node.parts[0] == "item":
            return _resolve_iteration_item_reference(node.parts, workflow=workflow)
        if node.parts[0] == "args":
            return _resolve_args_reference(node.parts, workflow=workflow)
        return _resolve_input_reference(node.parts, workflow=workflow)
    if isinstance(node, StateReferenceNode):
        return _resolve_state_reference(node, parsed=parsed, workflow=workflow)
    if isinstance(node, StepReferenceNode):
        return _resolve_step_reference(node, parsed=parsed, step_results=step_results)
    if isinstance(node, ListNode):
        return [
            _evaluate_node(
                item,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
            for item in node.items
        ]
    if isinstance(node, ObjectEntryNode):
        return _evaluate_node(
            node.value,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
    if isinstance(node, ObjectNode):
        return {
            entry.key: _evaluate_node(
                entry.value,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
            for entry in node.entries
        }
    if isinstance(node, CallNode):
        return _evaluate_read_only_call(
            node,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
    if isinstance(node, AdapterInvocationNode):
        return _evaluate_adapter_invocation(
            node,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
    if isinstance(node, PipelineNode):
        value = _evaluate_node(
            node.source,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
        for filter_node in node.filters:
            if isinstance(filter_node, FilterApplicationNode):
                value = _apply_filter(
                    filter_node,
                    value,
                    parsed=parsed,
                    workflow=workflow,
                    context=context,
                    step_results=step_results,
                    observation_session=observation_session,
                )
                continue
            if isinstance(filter_node, AdapterInvocationNode):
                value = _evaluate_adapter_invocation_result(
                    filter_node,
                    parsed=parsed,
                    workflow=workflow,
                    context=context,
                    step_results=step_results,
                    observation_session=observation_session,
                    inherited_root=value,
                ).value
                continue
            raise ValueExpressionEvaluationError(
                code="runtime.value.pipeline_stage_invalid",
                message="Pipeline contains an unsupported stage",
                details={"expression": parsed.source, "stage_type": type(filter_node).__name__},
            )
        return value
    if isinstance(node, BuiltinCallNode):
        return _evaluate_builtin_call(
            node,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
    if isinstance(node, UnaryNode):
        value = _evaluate_node(
            node.operand,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
        if isinstance(value, bool):
            return not value
        raise ValueExpressionEvaluationError(
            code="runtime.value.boolean_operand_type",
            message=f"Operator '{node.operator}' requires a boolean operand",
            details={"expression": parsed.source, "operator": node.operator, "actual_type": type(value).__name__},
        )
    if isinstance(node, BinaryNode):
        if node.operator in {"==", "!=", "in", "not in"}:
            left = _evaluate_node(
                node.left,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
            right = _evaluate_node(
                node.right,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
            if node.operator == "==":
                return left == right
            if node.operator == "!=":
                return left != right
            if not isinstance(right, list):
                raise ValueExpressionEvaluationError(
                    code="runtime.value.comparison_operand_type",
                    message=f"Operator '{node.operator}' requires a list right operand",
                    details={"expression": parsed.source, "operator": node.operator, "actual_type": type(right).__name__},
                )
            return left in right if node.operator == "in" else left not in right
        left = _evaluate_node(
            node.left,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
        if not isinstance(left, bool):
            raise ValueExpressionEvaluationError(
                code="runtime.value.boolean_operand_type",
                message=f"Operator '{node.operator}' requires boolean operands",
                details={"expression": parsed.source, "operator": node.operator, "actual_type": type(left).__name__},
            )
        if node.operator == "and":
            if not left:
                return False
            right = _evaluate_node(
                node.right,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
            if isinstance(right, bool):
                return right
            raise ValueExpressionEvaluationError(
                code="runtime.value.boolean_operand_type",
                message=f"Operator '{node.operator}' requires boolean operands",
                details={"expression": parsed.source, "operator": node.operator, "actual_type": type(right).__name__},
            )
        if node.operator == "or":
            if left:
                return True
            right = _evaluate_node(
                node.right,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
            if isinstance(right, bool):
                return right
            raise ValueExpressionEvaluationError(
                code="runtime.value.boolean_operand_type",
                message=f"Operator '{node.operator}' requires boolean operands",
                details={"expression": parsed.source, "operator": node.operator, "actual_type": type(right).__name__},
            )
    raise ValueExpressionEvaluationError(
        code="runtime.value.expression_invalid",
        message="Value expression node is not evaluable",
        details={"expression": parsed.source, "node_type": type(node).__name__},
    )


def _resolve_input_reference(parts: tuple[str, ...], *, workflow: Workflow) -> JSONValue:
    try:
        return resolve_workflow_input_reference(parts, workflow)
    except RuntimeStateError as exc:
        raise ValueExpressionEvaluationError(
            code="runtime.value.reference_unknown" if exc.code == "runtime.state.reference_unknown" else "runtime.value.input_missing",
            message=exc.message,
            details=exc.details,
        ) from exc


def _resolve_iteration_item_reference(parts: tuple[str, ...], *, workflow: Workflow) -> JSONValue:
    if "__iteration_item__" not in workflow.inputs:
        raise ValueExpressionEvaluationError(
            code="runtime.value.input_missing",
            message=f"Workflow input reference '{'.'.join(parts)}' is missing",
            details={"reference": ".".join(parts)},
        )
    current: JSONValue = workflow.inputs["__iteration_item__"]
    for part in parts[1:]:
        if not isinstance(current, dict) or part not in current:
            raise ValueExpressionEvaluationError(
                code="runtime.value.input_missing",
                message=f"Workflow input reference '{'.'.join(parts)}' is missing",
                details={"reference": ".".join(parts)},
            )
        current = current[part]
    return current


def _resolve_args_reference(parts: tuple[str, ...], *, workflow: Workflow) -> JSONValue:
    if "__fragment_args__" not in workflow.inputs:
        raise ValueExpressionEvaluationError(
            code="runtime.value.reference_unknown",
            message="Unknown object 'args'",
            details={"reference": ".".join(parts), "object": "args"},
        )
    current: JSONValue = workflow.inputs["__fragment_args__"]
    if not isinstance(current, dict):
        raise ValueExpressionEvaluationError(
            code="runtime.value.reference_unknown",
            message="Unknown object 'args'",
            details={"reference": ".".join(parts), "object": "args"},
        )
    for part in parts[1:]:
        if not isinstance(current, dict) or part not in current:
            raise ValueExpressionEvaluationError(
                code="runtime.value.input_missing",
                message=f"Workflow input reference '{'.'.join(parts)}' is missing",
                details={"reference": ".".join(parts)},
            )
        current = current[part]
    return current


def _resolve_state_reference(node: StateReferenceNode, *, parsed: ParsedValueExpression, workflow: Workflow) -> JSONValue:
    expression = render_expression_text(node, source=parsed.source)
    try:
        target = resolve_state_target(expression, workflow)
    except RuntimeStateError as exc:
        raise ValueExpressionEvaluationError(
            code=(
                "runtime.value.state_path_invalid"
                if exc.code == "runtime.state.path_invalid"
                else "runtime.value.state_key_invalid"
                if exc.code == "runtime.state.key_invalid"
                else "runtime.value.input_missing"
                if exc.code == "runtime.state.input_missing"
                else exc.code
            ),
            message=exc.message,
            details=exc.details,
        ) from exc
    try:
        document = read_state_document(target.location)
        value = read_state_value(document, key=target.key, fields=target.fields)
    except RuntimeStateError as exc:
        raise ValueExpressionEvaluationError(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ) from exc
    if value is None:
        raise ValueExpressionEvaluationError(
            code="runtime.value.state_missing",
            message="Runtime state value is missing",
            details={"expression": expression, "state": target.location.name, "key": target.key, "fields": list(target.fields)},
        )
    return value


def _resolve_step_reference(node: StepReferenceNode, *, parsed: ParsedValueExpression, step_results: dict[str, OperationResult | JSONObject]) -> JSONValue:
    result = step_results.get(node.register)
    if result is None:
        raise ValueExpressionEvaluationError(
            code="runtime.value.step_missing",
            message=f"Registered step '{node.register}' is not available",
            details={"expression": parsed.source, "register": node.register},
        )
    if isinstance(result, OperationResult):
        current: JSONValue = {"status": result.status, "summary": result.summary, "outputs": result.outputs}
    else:
        current = result
    for field in node.fields:
        if not isinstance(current, dict) or field not in current:
            raise ValueExpressionEvaluationError(
                code="runtime.value.step_field_missing",
                message=f"Registered step field '{field}' is not available",
                details={"expression": parsed.source, "register": node.register, "fields": list(node.fields)},
            )
        current = current[field]
    return current


def _apply_filter(
    filter_node: FilterApplicationNode,
    value: JSONValue,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    spec = VALUE_EXPRESSION_FILTERS.get(filter_node.name)
    if spec is not None:
        return spec.handler(value, filter_node, parsed, workflow, {"context": context, "step_results": step_results, "observation_session": observation_session})
    raise ValueExpressionEvaluationError(
        code="runtime.value.filter_unknown",
        message=f"Unknown local-expression filter '{filter_node.name}'",
        details={"expression": parsed.source, "filter": filter_node.name},
    )


def _evaluate_builtin_call(
    node: BuiltinCallNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    spec = VALUE_EXPRESSION_BUILTINS.get(node.name)
    if spec is not None:
        if node.name in {"is_missing", "is_present"}:
            return _evaluate_presence_builtin(
                node,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
        return spec.handler(
            node,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
    raise ValueExpressionEvaluationError(
        code="runtime.value.expression_builtin_unsupported",
        message=f"Built-in value expression '{node.name}' is not supported yet",
        details={"expression": parsed.source, "builtin": node.name},
    )


def _evaluate_format_call(
    node: BuiltinCallNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    if not node.arguments:
        raise ValueExpressionEvaluationError(
            code="runtime.value.format_args_invalid",
            message="Built-in value expression 'format' requires a template argument",
            details={"expression": parsed.source, "builtin": node.name},
        )
    template = _evaluate_node(
        node.arguments[0],
        parsed=parsed,
        workflow=workflow,
        context=context,
        step_results=step_results,
        observation_session=observation_session,
    )
    if not isinstance(template, str):
        raise ValueExpressionEvaluationError(
            code="runtime.value.format_template_invalid",
            message="Built-in value expression 'format' requires a string template",
            details={"expression": parsed.source, "builtin": node.name, "actual_type": type(template).__name__},
        )
    values = tuple(
        _evaluate_node(
            argument,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
        for argument in node.arguments[1:]
    )
    placeholder_count = template.count("{}")
    if placeholder_count != len(values):
        raise ValueExpressionEvaluationError(
            code="runtime.value.format_args_invalid",
            message="Built-in value expression 'format' received the wrong number of arguments",
            details={"expression": parsed.source, "builtin": node.name, "placeholders": placeholder_count, "arguments": len(values)},
        )
    return template.format(*tuple(_coerce_format_value(value) for value in values))


def _evaluate_presence_builtin(
    node: BuiltinCallNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    if len(node.arguments) != 1:
        raise ValueExpressionEvaluationError(
            code="runtime.value.presence_check_arity",
            message=f"Built-in value expression '{node.name}' requires exactly one argument",
            details={"expression": parsed.source, "builtin": node.name},
        )
    argument = node.arguments[0]
    normalized_argument = argument
    if isinstance(argument, ReferenceNode):
        from ordo.runtime.local_expressions import LOCAL_EXPRESSION_PARSE_ERRORS, resolve_workflow_let_reference_node

        try:
            expanded = resolve_workflow_let_reference_node(argument, workflow, context=context)
        except LOCAL_EXPRESSION_PARSE_ERRORS:
            expanded = None
        if expanded is not None:
            normalized_argument = expanded
    if not _is_presence_check_argument(normalized_argument):
        raise ValueExpressionEvaluationError(
            code="runtime.value.presence_check_argument",
            message=f"Built-in value expression '{node.name}' requires a lookup-style reference or read-only adapter invocation argument",
            details={"expression": parsed.source, "builtin": node.name},
        )
    if isinstance(normalized_argument, PipelineNode):
        try:
            _evaluate_node(
                normalized_argument,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
        except ValueExpressionEvaluationError as exc:
            if exc.code == "runtime.value.adapter_not_found":
                return True if node.name == "is_missing" else False
            raise
        return False if node.name == "is_missing" else True
    if isinstance(normalized_argument, AdapterInvocationNode):
        try:
            result = _evaluate_adapter_invocation_result(
                normalized_argument,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            )
        except ValueExpressionEvaluationError as exc:
            if exc.code == "runtime.value.adapter_not_found":
                return True if node.name == "is_missing" else False
            raise
        if result.kind != "read":
            raise ValueExpressionEvaluationError(
                code="runtime.value.presence_check_argument",
                message=f"Built-in value expression '{node.name}' requires a read-only adapter invocation argument",
                details={"expression": parsed.source, "builtin": node.name},
            )
        return False if node.name == "is_missing" else True
    missing = _is_reference_missing(normalized_argument, parsed=parsed, workflow=workflow, context=context, step_results=step_results)
    return missing if node.name == "is_missing" else not missing


def _evaluate_read_only_call(
    node: CallNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    if observation_session is None:
        raise ValueExpressionEvaluationError(
            code="runtime.value.call_unsupported",
            message="Read-only probe calls require a shared observation session in canonical value evaluation",
            details={"expression": parsed.source, "target": ".".join(node.target.parts)},
        )
    arguments = tuple(
        (
            argument.name,
            _evaluate_node(
                argument.value,
                parsed=parsed,
                workflow=workflow,
                context=context,
                step_results=step_results,
                observation_session=observation_session,
            ),
        )
        for argument in node.arguments
    )
    observation = observation_session.observe(
        ConditionObservationRequest(
            expression_text=render_expression_text(node, source=parsed.source),
            target=node.target.parts,
            fields=node.fields,
            arguments=arguments,
        )
    ).result
    if observation.status != "ok":
        details: JSONObject = {"expression": parsed.source, "target": ".".join(node.target.parts)}
        if observation.reference is not None:
            details["reference"] = observation.reference
        raise ValueExpressionEvaluationError(
            code="runtime.value.call_probe_failed",
            message=f"Read-only probe call '{'.'.join(node.target.parts)}' failed during value evaluation",
            details=details,
        )
    return observation.value


def _evaluate_adapter_invocation_result(
    node: AdapterInvocationNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
    inherited_root: JSONValue | None = None,
) -> RepresentationAdapterResult:
    parameters: JSONObject = {}
    for binding in node.bindings:
        parameters[binding.name] = _evaluate_node(
            binding.value,
            parsed=parsed,
            workflow=workflow,
            context=context,
            step_results=step_results,
            observation_session=observation_session,
        )
    if "root" in parameters:
        root_value = parameters.pop("root")
    elif inherited_root is not None:
        root_value = inherited_root
    else:
        raise ValueExpressionEvaluationError(
            code="runtime.value.adapter_root_missing",
            message=f"Representation-adapter family '{node.family}' requires outer binding 'root'",
            details={"expression": parsed.source, "family": node.family},
        )
    try:
        return evaluate_representation_adapter_invocation(
            RepresentationAdapterInvocation(
                family=node.family,
                body=node.body,
                root_value=root_value,
                parameters=parameters,
                source_expression=parsed.source[node.start : node.end],
            )
        )
    except RepresentationAdapterError as exc:
        raise ValueExpressionEvaluationError(code=exc.code, message=exc.message, details=exc.details) from exc


def _evaluate_adapter_invocation(
    node: AdapterInvocationNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    return _evaluate_adapter_invocation_result(
        node,
        parsed=parsed,
        workflow=workflow,
        context=context,
        step_results=step_results,
        observation_session=observation_session,
    ).value


def _require_string(value: JSONValue, *, filter_name: str, parsed: ParsedValueExpression) -> str:
    if isinstance(value, str):
        return value
    raise ValueExpressionEvaluationError(
        code="runtime.value.filter_type_invalid",
        message=f"Filter '{filter_name}' requires a string input",
        details={"expression": parsed.source, "filter": filter_name, "actual_type": type(value).__name__},
    )


def _is_number_value(value: JSONValue) -> bool:
    return type(value) in {int, float}


def _is_integer_value(value: JSONValue) -> bool:
    return type(value) is int


def _json_strict_equal(left: JSONValue, right: JSONValue) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return str(left) == str(right)
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        assert isinstance(right, list)
        return len(left) == len(right) and all(_json_strict_equal(left_item, right_item) for left_item, right_item in zip(left, right, strict=False))
    if isinstance(left, dict):
        assert isinstance(right, dict)
        return left.keys() == right.keys() and all(_json_strict_equal(left[key], right[key]) for key in left)
    return left == right


def _slugify(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", lowered)
    return normalized.strip("-")


def _parse_field_path(path: str) -> tuple[FieldPathSegment, ...]:
    if not path:
        raise _FieldPathSyntaxError("Filter 'field' requires a non-empty path", 0)
    segments: list[FieldPathSegment] = []
    position = 0
    length = len(path)

    def consume_identifier(start: int) -> tuple[str, int]:
        if start >= length or not (path[start].isalpha() or path[start] == "_"):
            raise _FieldPathSyntaxError("Filter 'field' path must start with an identifier", start)
        end = start + 1
        while end < length and (path[end].isalnum() or path[end] == "_"):
            end += 1
        return path[start:end], end

    identifier, position = consume_identifier(position)
    segments.append(identifier)
    while position < length:
        char = path[position]
        if char == ".":
            identifier, position = consume_identifier(position + 1)
            segments.append(identifier)
            continue
        if char == "[":
            closing = path.find("]", position + 1)
            if closing == -1:
                raise _FieldPathSyntaxError("Filter 'field' path index is missing a closing bracket", position)
            raw_index = path[position + 1 : closing]
            if not raw_index or any(not item.isdigit() for item in raw_index):
                raise _FieldPathSyntaxError("Filter 'field' path indexes must be zero-based integers", position + 1)
            segments.append(int(raw_index))
            position = closing + 1
            continue
        raise _FieldPathSyntaxError("Filter 'field' path contains unsupported syntax", position)
    return tuple(segments)


def _resolve_field_path(value: JSONValue, path: tuple[FieldPathSegment, ...]) -> JSONValue | object:
    current: JSONValue | object = value
    for segment in path:
        if isinstance(segment, str):
            if not isinstance(current, dict) or segment not in current:
                return _FIELD_PATH_MISSING
            current = current[segment]
            continue
        if not isinstance(current, list) or segment < 0 or segment >= len(current):
            return _FIELD_PATH_MISSING
        current = current[segment]
    return current


def _require_list(value: JSONValue, *, filter_name: str, parsed: ParsedValueExpression) -> list[JSONValue]:
    if isinstance(value, list):
        return value
    raise ValueExpressionEvaluationError(
        code="runtime.value.filter_type_invalid",
        message=f"Filter '{filter_name}' requires an array input",
        details={"expression": parsed.source, "filter": filter_name, "actual_type": type(value).__name__},
    )


def _require_field_path(
    filter_node: FilterApplicationNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    evaluation_context: dict[str, object],
) -> tuple[str, tuple[FieldPathSegment, ...]]:
    raw_path = _evaluate_filter_argument(
        filter_node,
        0,
        parsed=parsed,
        workflow=workflow,
        context=_context_local_expression_context(evaluation_context),
        step_results=_context_step_results(evaluation_context),
        observation_session=_context_observation_session(evaluation_context),
    )
    if not isinstance(raw_path, str):
        raise ValueExpressionEvaluationError(
            code="runtime.value.filter_arg_type_invalid",
            message="Filter 'field' requires a string path argument",
            details={"expression": parsed.source, "filter": "field", "actual_type": type(raw_path).__name__},
        )
    try:
        return raw_path, _parse_field_path(raw_path)
    except _FieldPathSyntaxError as exc:
        raise ValueExpressionEvaluationError(
            code="runtime.value.field_path_invalid",
            message=exc.message,
            details={"expression": parsed.source, "filter": "field", "path": raw_path, "position": exc.position},
        ) from exc


def _apply_lower_filter(
    value: JSONValue,
    _filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    text = _require_string(value, filter_name="lower", parsed=parsed)
    return text.lower()


def _apply_trim_filter(
    value: JSONValue,
    _filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    text = _require_string(value, filter_name="trim", parsed=parsed)
    return text.strip()


def _apply_slug_filter(
    value: JSONValue,
    _filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    text = _require_string(value, filter_name="slug", parsed=parsed)
    return _slugify(text)


def _apply_is_string_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    return isinstance(value, str)


def _apply_is_number_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    return _is_number_value(value)


def _apply_is_integer_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    return _is_integer_value(value)


def _apply_is_boolean_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    return isinstance(value, bool)


def _evaluate_filter_argument(
    filter_node: FilterApplicationNode,
    index: int,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    try:
        argument = filter_node.arguments[index]
    except IndexError as exc:
        raise ValueExpressionEvaluationError(
            code="runtime.value.filter_args_invalid",
            message=f"Filter '{filter_node.name}' received the wrong number of arguments",
            details={"expression": parsed.source, "filter": filter_node.name, "arguments": len(filter_node.arguments)},
        ) from exc
    return _evaluate_node(
        argument,
        parsed=parsed,
        workflow=workflow,
        context=context,
        step_results=step_results,
        observation_session=observation_session,
    )


def _context_local_expression_context(evaluation_context: dict[str, object]):
    return evaluation_context.get("context")


def _context_step_results(evaluation_context: dict[str, object]) -> dict[str, OperationResult]:
    value = evaluation_context.get("step_results")
    return value if isinstance(value, dict) else {}


def _context_observation_session(evaluation_context: dict[str, object]) -> ReadOnlyObservationSession | None:
    value = evaluation_context.get("observation_session")
    return value if isinstance(value, ReadOnlyObservationSession) else None


def _require_no_extra_filter_arguments(filter_node: FilterApplicationNode, *, parsed: ParsedValueExpression, expected: int) -> None:
    if len(filter_node.arguments) != expected:
        raise ValueExpressionEvaluationError(
            code="runtime.value.filter_args_invalid",
            message=f"Filter '{filter_node.name}' received the wrong number of arguments",
            details={
                "expression": parsed.source,
                "filter": filter_node.name,
                "expected_arguments": expected,
                "arguments": len(filter_node.arguments),
            },
        )


def _apply_eq_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=1)
    expected_value = _evaluate_filter_argument(
        filter_node,
        0,
        parsed=parsed,
        workflow=workflow,
        context=_context_local_expression_context(evaluation_context),
        step_results=_context_step_results(evaluation_context),
        observation_session=_context_observation_session(evaluation_context),
    )
    return _json_strict_equal(value, expected_value)


def _apply_ne_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=1)
    expected_value = _evaluate_filter_argument(
        filter_node,
        0,
        parsed=parsed,
        workflow=workflow,
        context=_context_local_expression_context(evaluation_context),
        step_results=_context_step_results(evaluation_context),
        observation_session=_context_observation_session(evaluation_context),
    )
    return not _json_strict_equal(value, expected_value)


def _apply_in_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=1)
    container = _evaluate_filter_argument(
        filter_node,
        0,
        parsed=parsed,
        workflow=workflow,
        context=_context_local_expression_context(evaluation_context),
        step_results=_context_step_results(evaluation_context),
        observation_session=_context_observation_session(evaluation_context),
    )
    if not isinstance(container, list):
        raise ValueExpressionEvaluationError(
            code="runtime.value.filter_type_invalid",
            message="Filter 'in' requires a list container argument",
            details={
                "expression": parsed.source,
                "filter": "in",
                "actual_type": type(container).__name__,
            },
        )
    return any(_json_strict_equal(value, item) for item in container)


def _apply_field_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=1)
    raw_path, path = _require_field_path(
        filter_node,
        parsed=parsed,
        workflow=workflow,
        evaluation_context=evaluation_context,
    )
    if isinstance(value, dict):
        resolved = _resolve_field_path(value, path)
        if resolved is _FIELD_PATH_MISSING:
            raise ValueExpressionEvaluationError(
                code="runtime.value.field_path_missing",
                message="Filter 'field' could not resolve the addressed path on object input",
                details={"expression": parsed.source, "filter": "field", "path": raw_path},
            )
        return resolved
    if isinstance(value, list):
        projected: list[JSONValue] = []
        for item in value:
            resolved = _resolve_field_path(item, path)
            projected.append(None if resolved is _FIELD_PATH_MISSING else resolved)
        return projected
    raise ValueExpressionEvaluationError(
        code="runtime.value.filter_type_invalid",
        message="Filter 'field' requires an object or array input",
        details={"expression": parsed.source, "filter": "field", "actual_type": type(value).__name__},
    )


def _apply_lookup_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=1)
    raw_key = _evaluate_filter_argument(
        filter_node,
        0,
        parsed=parsed,
        workflow=workflow,
        context=_context_local_expression_context(evaluation_context),
        step_results=_context_step_results(evaluation_context),
        observation_session=_context_observation_session(evaluation_context),
    )
    if not isinstance(raw_key, str):
        raise ValueExpressionEvaluationError(
            code="runtime.value.filter_arg_type_invalid",
            message="Filter 'lookup' requires a string key argument",
            details={"expression": parsed.source, "filter": "lookup", "actual_type": type(raw_key).__name__},
        )
    if not isinstance(value, dict):
        raise ValueExpressionEvaluationError(
            code="runtime.value.filter_type_invalid",
            message="Filter 'lookup' requires an object input",
            details={"expression": parsed.source, "filter": "lookup", "actual_type": type(value).__name__},
        )
    if raw_key not in value:
        raise ValueExpressionEvaluationError(
            code="runtime.value.lookup_key_missing",
            message="Filter 'lookup' could not resolve the addressed key on object input",
            details={"expression": parsed.source, "filter": "lookup", "key": raw_key},
        )
    return value[raw_key]


def _apply_flatten_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    items = _require_list(value, filter_name="flatten", parsed=parsed)
    flattened: list[JSONValue] = []
    for item in items:
        if isinstance(item, list):
            flattened.extend(item)
        else:
            flattened.append(item)
    return flattened


def _apply_first_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    items = _require_list(value, filter_name="first", parsed=parsed)
    return items[0] if items else None


def _apply_last_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    items = _require_list(value, filter_name="last", parsed=parsed)
    return items[-1] if items else None


def _apply_length_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    if isinstance(value, (list, str, dict)):
        return len(value)
    raise ValueExpressionEvaluationError(
        code="runtime.value.filter_type_invalid",
        message="Filter 'length' requires an array, object, or string input",
        details={"expression": parsed.source, "filter": "length", "actual_type": type(value).__name__},
    )


def _json_normalized_key(value: JSONValue) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _apply_unique_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    items = _require_list(value, filter_name="unique", parsed=parsed)
    seen: set[str] = set()
    unique_items: list[JSONValue] = []
    for item in items:
        key = _json_normalized_key(item)
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items


def _apply_only_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=1)
    predicate = filter_node.arguments[0]
    if not isinstance(predicate, OnlyPredicateNode):
        raise ValueExpressionEvaluationError(
            code="runtime.value.filter_args_invalid",
            message="Filter 'only' requires one field=value or field!=value predicate",
            details={"expression": parsed.source, "filter": "only"},
        )
    items = _require_list(value, filter_name="only", parsed=parsed)
    expected = _evaluate_node(
        predicate.expected,
        parsed=parsed,
        workflow=workflow,
        context=_context_local_expression_context(evaluation_context),
        step_results=_context_step_results(evaluation_context),
        observation_session=_context_observation_session(evaluation_context),
    )
    path = _parse_field_path(predicate.path)
    kept: list[JSONValue] = []
    for item in items:
        resolved = _resolve_field_path(item, path)
        if resolved is _FIELD_PATH_MISSING:
            continue
        if predicate.operator == "=" and _json_strict_equal(resolved, expected):
            kept.append(item)
            continue
        if predicate.operator == "!=" and not _json_strict_equal(resolved, expected):
            kept.append(item)
    return kept


def _apply_not_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _evaluation_context: dict[str, object],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=0)
    if isinstance(value, bool):
        return not value
    raise ValueExpressionEvaluationError(
        code="runtime.value.filter_type_invalid",
        message="Filter 'not' requires a boolean input",
        details={"expression": parsed.source, "filter": "not", "actual_type": type(value).__name__},
    )


def _is_presence_check_argument(node: ValueExpressionNode) -> bool:
    if isinstance(node, ReferenceNode):
        return bool(node.parts) and node.parts[0] in {"inputs", "args"} and len(node.parts) >= 2
    if isinstance(node, AdapterInvocationNode):
        return True
    if isinstance(node, PipelineNode):
        return all(isinstance(stage, AdapterInvocationNode) for stage in node.filters)
    return isinstance(node, (StateReferenceNode, StepReferenceNode))


def _is_reference_missing(
    node: ValueExpressionNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    context,
    step_results: dict[str, OperationResult],
) -> bool:
    if isinstance(node, ReferenceNode):
        from ordo.runtime.local_expressions import LOCAL_EXPRESSION_PARSE_ERRORS, resolve_workflow_let_reference_node

        try:
            expanded = resolve_workflow_let_reference_node(node, workflow, context=context)
        except LOCAL_EXPRESSION_PARSE_ERRORS:
            return True
        if expanded is not None:
            return _is_reference_missing(expanded, parsed=parsed, workflow=workflow, context=context, step_results=step_results)
        if not node.parts or node.parts[0] != "inputs":
            return True
        current: JSONValue = workflow.inputs
        parts = node.parts
        for part in parts[1:]:
            if not isinstance(current, dict) or part not in current:
                return True
            current = current[part]
        return False
    if isinstance(node, StepReferenceNode):
        result = step_results.get(node.register)
        if result is None:
            return True
        current: JSONValue = {"status": result.status, "summary": result.summary, "outputs": result.outputs}
        for field in node.fields:
            if not isinstance(current, dict) or field not in current:
                return True
            current = current[field]
        return False
    if isinstance(node, StateReferenceNode):
        try:
            target = resolve_state_target(render_expression_text(node, source=parsed.source), workflow)
            document = read_state_document(target.location)
            value = read_state_value(document, key=target.key, fields=target.fields)
            return value is None
        except RuntimeStateError:
            return True
    return True


def render_expression_text(node: ValueExpressionNode, *, source: str) -> str:
    if isinstance(node, LiteralNode):
        return json.dumps(node.value)
    if isinstance(node, ReferenceNode):
        return ".".join(node.parts)
    if isinstance(node, StateReferenceNode):
        key_reference = ".".join(node.key_reference)
        suffix = "" if not node.fields else "." + ".".join(node.fields)
        return f"state.{node.state_role}[{key_reference}]{suffix}"
    if isinstance(node, StepReferenceNode):
        suffix = "" if not node.fields else "." + ".".join(node.fields)
        return f"step.{node.register}{suffix}"
    if isinstance(node, ListNode):
        return "[" + ", ".join(render_expression_text(item, source=source) for item in node.items) + "]"
    if isinstance(node, ObjectEntryNode):
        key = node.key if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", node.key) else json.dumps(node.key)
        return f"{key}:" + render_expression_text(node.value, source=source)
    if isinstance(node, ObjectNode):
        return "{" + ", ".join(render_expression_text(entry, source=source) for entry in node.entries) + "}"
    if isinstance(node, CallArgumentNode):
        return f"{node.name}=" + render_expression_text(node.value, source=source)
    if isinstance(node, CallNode):
        args = ", ".join(render_expression_text(argument, source=source) for argument in node.arguments)
        suffix = "" if not node.fields else "." + ".".join(node.fields)
        target = ".".join(node.target.parts)
        return f"{target}({args}){suffix}"
    if isinstance(node, FilterApplicationNode):
        if not node.arguments:
            return node.name
        args = ", ".join(render_expression_text(argument, source=source) for argument in node.arguments)
        return f"{node.name}({args})"
    if isinstance(node, OnlyPredicateNode):
        return f"{node.path}{node.operator}" + render_expression_text(node.expected, source=source)
    if isinstance(node, PipelineNode):
        parts = [render_expression_text(node.source, source=source)]
        parts.extend(render_expression_text(filter_node, source=source) for filter_node in node.filters)
        return " | ".join(parts)
    if isinstance(node, BuiltinCallNode):
        args = ", ".join(render_expression_text(argument, source=source) for argument in node.arguments)
        return f"{node.name}({args})"
    if isinstance(node, UnaryNode):
        return f"{node.operator} " + render_expression_text(node.operand, source=source)
    if isinstance(node, BinaryNode):
        left = render_expression_text(node.left, source=source)
        right = render_expression_text(node.right, source=source)
        return f"{left} {node.operator} {right}"
    if isinstance(node, AdapterBindingNode):
        return f"{node.name}=" + render_expression_text(node.value, source=source)
    if isinstance(node, AdapterInvocationNode):
        bindings = ""
        if node.bindings:
            bindings = "(" + ", ".join(render_expression_text(binding, source=source) for binding in node.bindings) + ")"
        return f"{node.family}{bindings} -> {node.body}"
    return source[node.start : node.end]

VALUE_EXPRESSION_FILTERS: dict[str, ValueExpressionFilterSpec] = build_filter_registry(
    ValueExpressionFilterSpec(name="lower", input_type="string", output_type="string", argument_count=0, handler=_apply_lower_filter),
    ValueExpressionFilterSpec(name="trim", input_type="string", output_type="string", argument_count=0, handler=_apply_trim_filter),
    ValueExpressionFilterSpec(name="slug", input_type="string", output_type="string", argument_count=0, handler=_apply_slug_filter),
    ValueExpressionFilterSpec(name="eq", input_type="json", output_type="boolean", argument_count=1, handler=_apply_eq_filter),
    ValueExpressionFilterSpec(name="ne", input_type="json", output_type="boolean", argument_count=1, handler=_apply_ne_filter),
    ValueExpressionFilterSpec(name="not", input_type="boolean", output_type="boolean", argument_count=0, handler=_apply_not_filter),
    ValueExpressionFilterSpec(name="is_string", input_type="json", output_type="boolean", argument_count=0, handler=_apply_is_string_filter),
    ValueExpressionFilterSpec(name="is_number", input_type="json", output_type="boolean", argument_count=0, handler=_apply_is_number_filter),
    ValueExpressionFilterSpec(name="is_integer", input_type="json", output_type="boolean", argument_count=0, handler=_apply_is_integer_filter),
    ValueExpressionFilterSpec(name="is_boolean", input_type="json", output_type="boolean", argument_count=0, handler=_apply_is_boolean_filter),
    ValueExpressionFilterSpec(name="in", input_type="json", output_type="boolean", argument_count=1, handler=_apply_in_filter),
    ValueExpressionFilterSpec(name="field", input_type="json", output_type="json", argument_count=1, handler=_apply_field_filter),
    ValueExpressionFilterSpec(name="lookup", input_type="json", output_type="json", argument_count=1, handler=_apply_lookup_filter),
    ValueExpressionFilterSpec(name="only", input_type="json", output_type="json", argument_count=1, handler=_apply_only_filter, authored_form="only(field=value) / only(field!=value)"),
    ValueExpressionFilterSpec(name="flatten", input_type="json", output_type="json", argument_count=0, handler=_apply_flatten_filter),
    ValueExpressionFilterSpec(name="first", input_type="json", output_type="json", argument_count=0, handler=_apply_first_filter),
    ValueExpressionFilterSpec(name="last", input_type="json", output_type="json", argument_count=0, handler=_apply_last_filter),
    ValueExpressionFilterSpec(name="length", input_type="json", output_type="number", argument_count=0, handler=_apply_length_filter),
    ValueExpressionFilterSpec(name="unique", input_type="json", output_type="json", argument_count=0, handler=_apply_unique_filter),
)

VALUE_EXPRESSION_BUILTINS: dict[str, ValueExpressionBuiltinSpec] = build_builtin_registry(
    ValueExpressionBuiltinSpec(name="format", handler=_evaluate_format_call),
    ValueExpressionBuiltinSpec(name="is_missing", handler=_evaluate_format_call),
    ValueExpressionBuiltinSpec(name="is_present", handler=_evaluate_format_call),
)


def collect_step_references(node: ValueExpressionNode) -> tuple[StepReferenceNode, ...]:
    """Collect registered step-result references from a parsed local-expression tree."""

    refs: list[StepReferenceNode] = []

    def visit(current: ValueExpressionNode) -> None:
        if isinstance(current, StepReferenceNode):
            refs.append(current)
            return
        if isinstance(current, ListNode):
            for item in current.items:
                visit(item)
            return
        if isinstance(current, ObjectEntryNode):
            visit(current.value)
            return
        if isinstance(current, ObjectNode):
            for entry in current.entries:
                visit(entry)
            return
        if isinstance(current, CallArgumentNode):
            visit(current.value)
            return
        if isinstance(current, CallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, OnlyPredicateNode):
            visit(current.expected)
            return
        if isinstance(current, PipelineNode):
            visit(current.source)
            for filter_node in current.filters:
                if isinstance(filter_node, FilterApplicationNode):
                    for argument in filter_node.arguments:
                        visit(argument)
                    continue
                visit(filter_node)
            return
        if isinstance(current, BuiltinCallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, UnaryNode):
            visit(current.operand)
            return
        if isinstance(current, BinaryNode):
            visit(current.left)
            visit(current.right)

    visit(node)
    return tuple(refs)


def _coerce_format_value(value: JSONValue) -> JSONScalar:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueExpressionEvaluationError(
        code="runtime.value.format_arg_type_invalid",
        message="Built-in value expression 'format' requires scalar arguments",
        details={"actual_type": type(value).__name__},
    )


def _consume_string(text: str, start: int) -> int:
    quote = text[start]
    position = start + 1
    while position < len(text):
        char = text[position]
        if char == "\\":
            position += 2
            continue
        if char == quote:
            return position + 1
        position += 1
    raise ValueExpressionParseError("Unterminated string literal", start, len(text))


def _decode_string(token_text: str, start: int) -> str:
    try:
        return bytes(token_text[1:-1], "utf-8").decode("unicode_escape")
    except UnicodeDecodeError as exc:
        raise ValueExpressionParseError("Invalid string literal", start, start + len(token_text)) from exc


def _decode_number(token_text: str) -> int | float:
    return float(token_text) if "." in token_text else int(token_text)


# Preferred local-expression terminology.
EmbeddedValueExpressionNode = ValueExpressionNode
ParsedEmbeddedValueExpression = ParsedLocalExpressionTree
EmbeddedValueExpressionParseError = LocalExpressionParseError
EmbeddedValueExpressionEvaluationError = LocalExpressionEvaluationError
parse_embedded_value_expression = parse_local_expression_tree
evaluate_embedded_value_expression = evaluate_local_expression_tree
# Transitional low-level helper aliases.
parse_value_expression = parse_local_expression_tree
evaluate_value_expression = evaluate_local_expression_tree
validate_value_expression = validate_local_expression_tree
collect_value_expression_dependencies = collect_local_expression_dependencies
