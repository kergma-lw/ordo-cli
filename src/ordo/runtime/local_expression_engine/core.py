"""Internal model and parser for workflow value expressions."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, Literal

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONScalar, JSONValue
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow

from ..state import RuntimeStateError, read_state_document, read_state_value, resolve_state_target, resolve_workflow_input_reference
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
    """Base parsed value-expression node."""

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
class ParsedValueExpression:
    """Structured parsed representation of a string-form value expression."""

    source: str
    root: ValueExpressionNode


@dataclass(frozen=True, slots=True)
class ValueExpressionParseError(Exception):
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
class ValueExpressionEvaluationError(Exception):
    """Structured evaluation error for parsed value expressions."""

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
class _Token:
    kind: str
    text: str
    start: int
    end: int


def parse_value_expression(expression: str, *, allow_boolean_composition: bool = False) -> ParsedValueExpression:
    """Parse a string-form value expression into a structured tree."""

    parser = _Parser(expression, allow_boolean_composition=allow_boolean_composition)
    root = parser.parse()
    return ParsedValueExpression(source=expression, root=root)


def evaluate_value_expression(
    parsed: ParsedValueExpression,
    workflow: Workflow,
    *,
    step_results: dict[str, OperationResult] | None = None,
) -> JSONValue:
    """Evaluate a parsed value expression against workflow inputs and state."""

    return _evaluate_node(parsed.root, parsed=parsed, workflow=workflow, step_results={} if step_results is None else step_results)


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
            raise ValueExpressionParseError("Expected value-expression term", token.start, token.end)
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
    return node


def _evaluate_node(
    node: ValueExpressionNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    step_results: dict[str, OperationResult],
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
        return [_evaluate_node(item, parsed=parsed, workflow=workflow, step_results=step_results) for item in node.items]
    if isinstance(node, CallNode):
        raise ValueExpressionEvaluationError(
            code="runtime.value.call_unsupported",
            message="Read-only probe calls are not evaluable through the canonical value engine yet",
            details={"expression": parsed.source, "target": ".".join(node.target.parts)},
        )
    if isinstance(node, PipelineNode):
        value = _evaluate_node(node.source, parsed=parsed, workflow=workflow, step_results=step_results)
        for filter_node in node.filters:
            value = _apply_filter(filter_node, value, parsed=parsed, workflow=workflow, step_results=step_results)
        return value
    if isinstance(node, BuiltinCallNode):
        return _evaluate_builtin_call(node, parsed=parsed, workflow=workflow, step_results=step_results)
    if isinstance(node, UnaryNode):
        value = _evaluate_node(node.operand, parsed=parsed, workflow=workflow, step_results=step_results)
        if isinstance(value, bool):
            return not value
        raise ValueExpressionEvaluationError(
            code="runtime.value.boolean_operand_type",
            message=f"Operator '{node.operator}' requires a boolean operand",
            details={"expression": parsed.source, "operator": node.operator, "actual_type": type(value).__name__},
        )
    if isinstance(node, BinaryNode):
        if node.operator in {"==", "!=", "in", "not in"}:
            left = _evaluate_node(node.left, parsed=parsed, workflow=workflow, step_results=step_results)
            right = _evaluate_node(node.right, parsed=parsed, workflow=workflow, step_results=step_results)
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
        left = _evaluate_node(node.left, parsed=parsed, workflow=workflow, step_results=step_results)
        if not isinstance(left, bool):
            raise ValueExpressionEvaluationError(
                code="runtime.value.boolean_operand_type",
                message=f"Operator '{node.operator}' requires boolean operands",
                details={"expression": parsed.source, "operator": node.operator, "actual_type": type(left).__name__},
            )
        if node.operator == "and":
            if not left:
                return False
            right = _evaluate_node(node.right, parsed=parsed, workflow=workflow, step_results=step_results)
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
            right = _evaluate_node(node.right, parsed=parsed, workflow=workflow, step_results=step_results)
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
) -> JSONValue:
    spec = VALUE_EXPRESSION_FILTERS.get(filter_node.name)
    if spec is not None:
        return spec.handler(value, filter_node, parsed, workflow, step_results)
    raise ValueExpressionEvaluationError(
        code="runtime.value.filter_unknown",
        message=f"Unknown value-expression filter '{filter_node.name}'",
        details={"expression": parsed.source, "filter": filter_node.name},
    )


def _evaluate_builtin_call(
    node: BuiltinCallNode,
    *,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    step_results: dict[str, OperationResult],
) -> JSONValue:
    spec = VALUE_EXPRESSION_BUILTINS.get(node.name)
    if spec is not None:
        return spec.handler(node, parsed=parsed, workflow=workflow, step_results=step_results)
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
) -> JSONValue:
    if not node.arguments:
        raise ValueExpressionEvaluationError(
            code="runtime.value.format_args_invalid",
            message="Built-in value expression 'format' requires a template argument",
            details={"expression": parsed.source, "builtin": node.name},
        )
    template = _evaluate_node(node.arguments[0], parsed=parsed, workflow=workflow, step_results=step_results)
    if not isinstance(template, str):
        raise ValueExpressionEvaluationError(
            code="runtime.value.format_template_invalid",
            message="Built-in value expression 'format' requires a string template",
            details={"expression": parsed.source, "builtin": node.name, "actual_type": type(template).__name__},
        )
    values = tuple(_evaluate_node(argument, parsed=parsed, workflow=workflow, step_results=step_results) for argument in node.arguments[1:])
    placeholder_count = template.count("{}")
    if placeholder_count != len(values):
        raise ValueExpressionEvaluationError(
            code="runtime.value.format_args_invalid",
            message="Built-in value expression 'format' received the wrong number of arguments",
            details={"expression": parsed.source, "builtin": node.name, "placeholders": placeholder_count, "arguments": len(values)},
        )
    return template.format(*tuple(_coerce_format_value(value) for value in values))


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
    _step_results: dict[str, OperationResult],
) -> JSONValue:
    text = _require_string(value, filter_name="lower", parsed=parsed)
    return text.lower()


def _apply_trim_filter(
    value: JSONValue,
    _filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _step_results: dict[str, OperationResult],
) -> JSONValue:
    text = _require_string(value, filter_name="trim", parsed=parsed)
    return text.strip()


def _apply_slug_filter(
    value: JSONValue,
    _filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _step_results: dict[str, OperationResult],
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
) -> JSONValue:
    try:
        argument = filter_node.arguments[index]
    except IndexError as exc:
        raise ValueExpressionEvaluationError(
            code="runtime.value.filter_args_invalid",
            message=f"Filter '{filter_node.name}' received the wrong number of arguments",
            details={"expression": parsed.source, "filter": filter_node.name, "arguments": len(filter_node.arguments)},
        ) from exc
    return _evaluate_node(argument, parsed=parsed, workflow=workflow, step_results=step_results)


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
    step_results: dict[str, OperationResult],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=1)
    expected_value = _evaluate_filter_argument(filter_node, 0, parsed=parsed, workflow=workflow, step_results=step_results)
    return value == expected_value


def _apply_ne_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    workflow: Workflow,
    step_results: dict[str, OperationResult],
) -> JSONValue:
    _require_no_extra_filter_arguments(filter_node, parsed=parsed, expected=1)
    expected_value = _evaluate_filter_argument(filter_node, 0, parsed=parsed, workflow=workflow, step_results=step_results)
    return value != expected_value


def _apply_not_filter(
    value: JSONValue,
    filter_node: FilterApplicationNode,
    parsed: ParsedValueExpression,
    _workflow: Workflow,
    _step_results: dict[str, OperationResult],
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
    """Collect registered step-result references from a parsed value-expression tree."""

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
ParsedEmbeddedValueExpression = ParsedValueExpression
EmbeddedValueExpressionParseError = ValueExpressionParseError
EmbeddedValueExpressionEvaluationError = ValueExpressionEvaluationError
parse_embedded_value_expression = parse_value_expression
evaluate_embedded_value_expression = evaluate_value_expression
