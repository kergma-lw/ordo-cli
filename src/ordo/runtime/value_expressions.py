"""Internal model and parser for workflow value expressions."""

from __future__ import annotations

from dataclasses import dataclass
import re

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONScalar, JSONValue
from ordo.model.workflow import Workflow

from .state import RuntimeStateError, read_state_document, read_state_value, resolve_state_target, resolve_workflow_input_reference


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
    """Runtime-state read such as ``states.task_state[inputs.issue_ref].branch``."""

    state_name: str
    key_reference: tuple[str, ...]
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


def parse_value_expression(expression: str) -> ParsedValueExpression:
    """Parse a string-form value expression into a structured tree."""

    parser = _Parser(expression)
    root = parser.parse()
    return ParsedValueExpression(source=expression, root=root)


def evaluate_value_expression(parsed: ParsedValueExpression, workflow: Workflow) -> JSONValue:
    """Evaluate a parsed value expression against workflow inputs and state."""

    return _evaluate_node(parsed.root, parsed=parsed, workflow=workflow)


class _Parser:
    def __init__(self, text: str) -> None:
        self._text = text
        self._tokens = _tokenize(text)
        self._index = 0

    def parse(self) -> ValueExpressionNode:
        node = self._parse_pipeline()
        if self._peek().kind != "EOF":
            token = self._peek()
            raise ValueExpressionParseError("Unexpected trailing token", token.start, token.end)
        return node

    def _parse_pipeline(self) -> ValueExpressionNode:
        source = self._parse_primary()
        filters: list[FilterApplicationNode] = []
        while self._match("PIPE") is not None:
            name_token = self._consume("IDENT", "Expected filter name after '|'")
            filters.append(FilterApplicationNode(start=name_token.start, end=name_token.end, name=name_token.text))
        if not filters:
            return source
        return PipelineNode(start=source.start, end=filters[-1].end, source=source, filters=tuple(filters))

    def _parse_primary(self) -> ValueExpressionNode:
        token = self._peek()
        if token.kind == "STRING":
            self._advance()
            return LiteralNode(start=token.start, end=token.end, value=_decode_string(token.text, token.start))
        if token.kind == "NUMBER":
            self._advance()
            return LiteralNode(start=token.start, end=token.end, value=_decode_number(token.text))
        if token.kind != "IDENT":
            raise ValueExpressionParseError("Expected value-expression term", token.start, token.end)
        if self._peek_kind("IDENT", expected_text="states"):
            return self._parse_state_reference()
        if self._peek_kind("IDENT") and self._peek_kind("LPAREN", offset=1):
            return self._parse_builtin_call()
        return self._parse_dotted_reference()

    def _parse_builtin_call(self) -> BuiltinCallNode:
        name_token = self._consume("IDENT", "Expected built-in name")
        self._consume("LPAREN", "Expected '(' after built-in name")
        arguments: list[ValueExpressionNode] = []
        if self._peek().kind != "RPAREN":
            while True:
                arguments.append(self._parse_pipeline())
                if self._match("COMMA") is None:
                    break
        end = self._consume("RPAREN", "Expected ')' after built-in arguments").end
        return BuiltinCallNode(start=name_token.start, end=end, name=name_token.text, arguments=tuple(arguments))

    def _parse_dotted_reference(self) -> ReferenceNode:
        start_token = self._consume("IDENT", "Expected identifier")
        parts = [start_token.text]
        end = start_token.end
        while self._match("DOT") is not None:
            next_token = self._consume("IDENT", "Expected identifier after '.'")
            parts.append(next_token.text)
            end = next_token.end
        return ReferenceNode(start=start_token.start, end=end, parts=tuple(parts))

    def _parse_state_reference(self) -> StateReferenceNode:
        start = self._consume("IDENT", "Expected 'states'")
        self._consume("DOT", "Expected '.' after 'states'")
        state_name = self._consume("IDENT", "Expected state name")
        self._consume("LBRACKET", "Expected '[' after state name")
        key_reference = self._parse_dotted_reference()
        if key_reference.parts[0] != "inputs" or len(key_reference.parts) < 2:
            raise ValueExpressionParseError(
                "State path key reference must use dotted form such as 'inputs.issue_ref'",
                key_reference.start,
                key_reference.end,
            )
        self._consume("RBRACKET", "Expected ']' after state key reference")
        fields: list[str] = []
        end = state_name.end
        while self._match("DOT") is not None:
            field_token = self._consume("IDENT", "Expected field name after '.'")
            fields.append(field_token.text)
            end = field_token.end
        if fields:
            end = end
        else:
            end = self._previous().end if self._previous().kind == "RBRACKET" else state_name.end
        return StateReferenceNode(
            start=start.start,
            end=end,
            state_name=state_name.text,
            key_reference=key_reference.parts,
            fields=tuple(fields),
        )

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
        if char in {'"', "'"}:
            start = position
            position = _consume_string(text, position)
            tokens.append(_Token("STRING", text[start:position], start, position))
            continue
        if char.isdigit():
            start = position
            position += 1
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


def _evaluate_node(node: ValueExpressionNode, *, parsed: ParsedValueExpression, workflow: Workflow) -> JSONValue:
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, ReferenceNode):
        return _resolve_input_reference(node.parts, workflow=workflow)
    if isinstance(node, StateReferenceNode):
        return _resolve_state_reference(node, parsed=parsed, workflow=workflow)
    if isinstance(node, PipelineNode):
        value = _evaluate_node(node.source, parsed=parsed, workflow=workflow)
        for filter_node in node.filters:
            value = _apply_filter(filter_node, value, parsed=parsed)
        return value
    if isinstance(node, BuiltinCallNode):
        return _evaluate_builtin_call(node, parsed=parsed, workflow=workflow)
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


def _apply_filter(filter_node: FilterApplicationNode, value: JSONValue, *, parsed: ParsedValueExpression) -> JSONValue:
    name = filter_node.name
    if name == "lower":
        text = _require_string(value, filter_name=name, parsed=parsed)
        return text.lower()
    if name == "trim":
        text = _require_string(value, filter_name=name, parsed=parsed)
        return text.strip()
    if name == "slug":
        text = _require_string(value, filter_name=name, parsed=parsed)
        return _slugify(text)
    raise ValueExpressionEvaluationError(
        code="runtime.value.filter_unknown",
        message=f"Unknown value-expression filter '{name}'",
        details={"expression": parsed.source, "filter": name},
    )


def _evaluate_builtin_call(node: BuiltinCallNode, *, parsed: ParsedValueExpression, workflow: Workflow) -> JSONValue:
    if node.name == "format":
        return _evaluate_format_call(node, parsed=parsed, workflow=workflow)
    raise ValueExpressionEvaluationError(
        code="runtime.value.expression_builtin_unsupported",
        message=f"Built-in value expression '{node.name}' is not supported yet",
        details={"expression": parsed.source, "builtin": node.name},
    )


def _evaluate_format_call(node: BuiltinCallNode, *, parsed: ParsedValueExpression, workflow: Workflow) -> JSONValue:
    if not node.arguments:
        raise ValueExpressionEvaluationError(
            code="runtime.value.format_args_invalid",
            message="Built-in value expression 'format' requires a template argument",
            details={"expression": parsed.source, "builtin": node.name},
        )
    template = _evaluate_node(node.arguments[0], parsed=parsed, workflow=workflow)
    if not isinstance(template, str):
        raise ValueExpressionEvaluationError(
            code="runtime.value.format_template_invalid",
            message="Built-in value expression 'format' requires a string template",
            details={"expression": parsed.source, "builtin": node.name, "actual_type": type(template).__name__},
        )
    values = tuple(_evaluate_node(argument, parsed=parsed, workflow=workflow) for argument in node.arguments[1:])
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


def _decode_number(token_text: str) -> int:
    return int(token_text)
