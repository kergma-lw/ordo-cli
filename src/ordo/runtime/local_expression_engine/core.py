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
class PipelineNode(ValueExpressionNode):
    """Left-to-right pipeline of built-in filters over a source value."""

    source: ValueExpressionNode
    filters: tuple[FilterApplicationNode, ...] = ()


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

    kind: Literal["root"]
    name: str
    start: int
    end: int


# Transitional aliases retained while runtime callers move to canonical terminology.
LocalExpressionNode = ValueExpressionNode
ParsedValueExpression = ParsedLocalExpressionTree
ValueExpressionParseError = LocalExpressionParseError
ValueExpressionEvaluationError = LocalExpressionEvaluationError
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
    step_results: dict[str, OperationResult] | None = None,
    observation_session: ReadOnlyObservationSession | None = None,
) -> JSONValue:
    """Evaluate one canonical local-expression tree against workflow-visible data."""

    return _evaluate_node(
        parsed.root,
        parsed=parsed,
        workflow=workflow,
        step_results={} if step_results is None else step_results,
        observation_session=observation_session,
    )


def evaluate_condition_expression(
    parsed: ParsedLocalExpressionTree,
    workflow: Workflow,
    *,
    observe: Callable[[ConditionObservationRequest], ConditionObservationResult] | None = None,
    session: ReadOnlyObservationSession | None = None,
    step_results: dict[str, OperationResult | JSONObject] | None = None,
) -> ConditionEvaluationResult:
    """Evaluate a canonical condition expression, including read-only probe observations."""

    if session is None:
        if observe is None:
            raise ValueError("Condition evaluation requires either an observation session or an observe callback")
        session = ReadOnlyObservationSession(observe)
    evaluator = _ConditionEvaluator(
        parsed,
        workflow,
        observation_session=session,
        step_results={} if step_results is None else step_results,
    )
    return evaluator.evaluate()


def validate_local_expression_tree(parsed: ParsedLocalExpressionTree) -> tuple[LocalExpressionValidationIssue, ...]:
    """Validate semantic rules over the canonical local-expression tree."""

    validator = _SemanticValidator(parsed)
    return tuple(validator.validate())


def collect_local_expression_dependencies(node: ValueExpressionNode) -> tuple[LocalExpressionDependency, ...]:
    """Collect local-root dependencies from the canonical local-expression tree."""

    found: list[LocalExpressionDependency] = []

    def visit(current: ValueExpressionNode) -> None:
        if isinstance(current, ReferenceNode):
            if current.parts and current.parts[0] in {"inputs", "args", "state", "step"}:
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
        if isinstance(current, CallArgumentNode):
            visit(current.value)
            return
        if isinstance(current, CallNode):
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
    start = 0
    while start < len(expression) and expression[start].isspace():
        start += 1
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
    if probe >= len(expression) or expression[probe] not in "[{.":
        return None
    if expression[probe] == "." and not has_representation_adapter(family):
        return None

    body, bindings, end = _split_adapter_body_and_bindings(
        expression,
        body_start=family_end,
        allow_boolean_composition=allow_boolean_composition,
    )
    trailing = expression[end:]
    if trailing.strip():
        token_start = end + len(trailing) - len(trailing.lstrip())
        raise ValueExpressionParseError("Unexpected trailing token", token_start, len(expression))
    return AdapterInvocationNode(start=start, end=end, family=family, body=body, bindings=bindings)


def _split_adapter_body_and_bindings(
    text: str,
    *,
    body_start: int,
    allow_boolean_composition: bool,
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
        filters: list[FilterApplicationNode] = []
        while self._match("PIPE") is not None:
            name_token = self._consume("IDENT", "Expected filter name after '|'")
            arguments: list[ValueExpressionNode] = []
            end = name_token.end
            if self._match("LPAREN") is not None:
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

    def _parse_primary(self) -> ValueExpressionNode:
        token = self._peek()
        if token.kind == "LPAREN":
            self._advance()
            node = self._parse_or() if self._allow_boolean_composition else self._parse_pipeline()
            end = self._consume("RPAREN", "Expected ')' to close grouped expression")
            return _with_grouped_end(node, end.end)
        if token.kind == "LBRACKET":
            return self._parse_list()
        if token.kind == "STRING":
            self._advance()
            return LiteralNode(start=token.start, end=token.end, value=_decode_string(token.text, token.start))
        if token.kind == "NUMBER":
            self._advance()
            return LiteralNode(start=token.start, end=token.end, value=_decode_number(token.text))
        if token.kind != "IDENT":
            raise ValueExpressionParseError("Expected local-expression term", token.start, token.end)
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
    def __init__(self, parsed: ParsedValueExpression) -> None:
        self._parsed = parsed
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
        if isinstance(node, CallArgumentNode):
            self._visit(node.value)
            return
        if isinstance(node, CallNode):
            self._validate_call(node)
            return
        if isinstance(node, FilterApplicationNode):
            for argument in node.arguments:
                self._visit(argument)
            return
        if isinstance(node, PipelineNode):
            self._visit(node.source)
            for item in node.filters:
                self._visit(item)
            return
        if isinstance(node, BuiltinCallNode):
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

    def _error(self, code: str, message: str, node: ValueExpressionNode) -> None:
        self._errors.append(ValueExpressionValidationError(code=code, message=message, start=node.start, end=node.end))


class _ConditionEvaluator:
    def __init__(
        self,
        parsed: ParsedValueExpression,
        workflow: Workflow,
        *,
        observation_session: ReadOnlyObservationSession,
        step_results: dict[str, OperationResult | JSONObject],
    ) -> None:
        self._parsed = parsed
        self._workflow = workflow
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
        if isinstance(node, ReferenceNode):
            if node.parts[0] == "inputs":
                try:
                    value = _resolve_input_reference(node.parts, workflow=self._workflow)
                except ValueExpressionEvaluationError as exc:
                    self._diagnostics.append(exc.to_diagnostic())
                    self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="input", status="probe_failed", value=None))
                    return "probe_failed", None
                self._trace.append(ConditionTraceEntry(expr=self._expr(node), kind="input", status="ok", value=value))
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
        return self._parsed.source[node.start : node.end]


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
            while position < length and (text[position].isalnum() or text[position] == "_" or text[position] == "-"):
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
    if isinstance(node, CallArgumentNode):
        return CallArgumentNode(start=node.start, end=end, name=node.name, value=node.value)
    if isinstance(node, CallNode):
        return CallNode(start=node.start, end=end, target=node.target, arguments=node.arguments, fields=node.fields)
    if isinstance(node, PipelineNode):
        return PipelineNode(start=node.start, end=end, source=node.source, filters=node.filters)
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
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, ReferenceNode):
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
                step_results=step_results,
                observation_session=observation_session,
            )
            for item in node.items
        ]
    if isinstance(node, CallNode):
        return _evaluate_read_only_call(
            node,
            parsed=parsed,
            workflow=workflow,
            step_results=step_results,
            observation_session=observation_session,
        )
    if isinstance(node, AdapterInvocationNode):
        return _evaluate_adapter_invocation(
            node,
            parsed=parsed,
            workflow=workflow,
            step_results=step_results,
            observation_session=observation_session,
        )
    if isinstance(node, PipelineNode):
        value = _evaluate_node(
            node.source,
            parsed=parsed,
            workflow=workflow,
            step_results=step_results,
            observation_session=observation_session,
        )
        for filter_node in node.filters:
            value = _apply_filter(
                filter_node,
                value,
                parsed=parsed,
                workflow=workflow,
                step_results=step_results,
                observation_session=observation_session,
            )
        return value
    if isinstance(node, BuiltinCallNode):
        return _evaluate_builtin_call(
            node,
            parsed=parsed,
            workflow=workflow,
            step_results=step_results,
            observation_session=observation_session,
        )
    if isinstance(node, UnaryNode):
        value = _evaluate_node(
            node.operand,
            parsed=parsed,
            workflow=workflow,
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
                step_results=step_results,
                observation_session=observation_session,
            )
            right = _evaluate_node(
                node.right,
                parsed=parsed,
                workflow=workflow,
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
            code="runtime.value.input_missing",
            message=exc.message,
            details=exc.details,
        ) from exc


def _resolve_state_reference(node: StateReferenceNode, *, parsed: ParsedValueExpression, workflow: Workflow) -> JSONValue:
    expression = parsed.source[node.start : node.end]
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
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    spec = VALUE_EXPRESSION_FILTERS.get(filter_node.name)
    if spec is not None:
        return spec.handler(value, filter_node, parsed, workflow, {"step_results": step_results, "observation_session": observation_session})
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
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    spec = VALUE_EXPRESSION_BUILTINS.get(node.name)
    if spec is not None:
        return spec.handler(
            node,
            parsed=parsed,
            workflow=workflow,
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


def _evaluate_read_only_call(
    node: CallNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
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
                step_results=step_results,
                observation_session=observation_session,
            ),
        )
        for argument in node.arguments
    )
    observation = observation_session.observe(
        ConditionObservationRequest(
            expression_text=parsed.source[node.start : node.end],
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


def _evaluate_adapter_invocation(
    node: AdapterInvocationNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    step_results: dict[str, OperationResult],
    observation_session: ReadOnlyObservationSession | None,
) -> JSONValue:
    parameters: JSONObject = {}
    for binding in node.bindings:
        parameters[binding.name] = _evaluate_node(
            binding.value,
            parsed=parsed,
            workflow=workflow,
            step_results=step_results,
            observation_session=observation_session,
        )
    if "root" not in parameters:
        raise ValueExpressionEvaluationError(
            code="runtime.value.adapter_root_missing",
            message=f"Representation-adapter family '{node.family}' requires outer binding 'root'",
            details={"expression": parsed.source, "family": node.family},
        )
    root_value = parameters.pop("root")
    try:
        result = evaluate_representation_adapter_invocation(
            RepresentationAdapterInvocation(
                family=node.family,
                body=node.body,
                root_value=root_value,
                parameters=parameters,
                source_expression=parsed.source[node.start : node.end],
            )
        )
        return result.value
    except RepresentationAdapterError as exc:
        raise ValueExpressionEvaluationError(code=exc.code, message=exc.message, details=exc.details) from exc


def _require_string(value: JSONValue, *, filter_name: str, parsed: ParsedValueExpression) -> str:
    if isinstance(value, str):
        return value
    raise ValueExpressionEvaluationError(
        code="runtime.value.filter_type_invalid",
        message=f"Filter '{filter_name}' requires a string input",
        details={"expression": parsed.source, "filter": filter_name, "actual_type": type(value).__name__},
    )


def _slugify(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", lowered)
    return normalized.strip("-")


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


def _evaluate_filter_argument(
    filter_node: FilterApplicationNode,
    index: int,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
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
        step_results=step_results,
        observation_session=observation_session,
    )


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
        step_results=_context_step_results(evaluation_context),
        observation_session=_context_observation_session(evaluation_context),
    )
    return value == expected_value


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
        step_results=_context_step_results(evaluation_context),
        observation_session=_context_observation_session(evaluation_context),
    )
    return value != expected_value


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
VALUE_EXPRESSION_FILTERS: dict[str, ValueExpressionFilterSpec] = build_filter_registry(
    ValueExpressionFilterSpec(name="lower", input_type="string", output_type="string", handler=_apply_lower_filter),
    ValueExpressionFilterSpec(name="trim", input_type="string", output_type="string", handler=_apply_trim_filter),
    ValueExpressionFilterSpec(name="slug", input_type="string", output_type="string", handler=_apply_slug_filter),
    ValueExpressionFilterSpec(name="eq", input_type="json", output_type="boolean", handler=_apply_eq_filter),
    ValueExpressionFilterSpec(name="ne", input_type="json", output_type="boolean", handler=_apply_ne_filter),
    ValueExpressionFilterSpec(name="not", input_type="boolean", output_type="boolean", handler=_apply_not_filter),
)

VALUE_EXPRESSION_BUILTINS: dict[str, ValueExpressionBuiltinSpec] = build_builtin_registry(
    ValueExpressionBuiltinSpec(name="format", handler=_evaluate_format_call),
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
        if isinstance(current, CallArgumentNode):
            visit(current.value)
            return
        if isinstance(current, CallNode):
            for argument in current.arguments:
                visit(argument)
            return
        if isinstance(current, PipelineNode):
            visit(current.source)
            for filter_node in current.filters:
                for argument in filter_node.arguments:
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


def parse_condition_expression(expression: str) -> ParsedValueExpression:
    return parse_local_expression_tree(expression, allow_boolean_composition=True)


def validate_parsed_condition_expression(parsed: ParsedValueExpression) -> tuple[ValueExpressionValidationError, ...]:
    return validate_local_expression_tree(parsed)


ConditionExpressionNode = ValueExpressionNode
ParsedConditionExpression = ParsedValueExpression
ConditionExpressionParseError = ValueExpressionParseError
ConditionExpressionValidationError = ValueExpressionValidationError


# Transitional low-level helper aliases.
parse_value_expression = parse_local_expression_tree
evaluate_value_expression = evaluate_local_expression_tree
validate_value_expression = validate_local_expression_tree
collect_value_expression_dependencies = collect_local_expression_dependencies
