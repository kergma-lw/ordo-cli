"""Parsing support for string-form guard expressions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ordo.model.diagnostic import Diagnostic


ExpressionOperator = Literal["and", "or", "==", "!=", "in", "not in"]


@dataclass(frozen=True, slots=True)
class GuardExpressionNode:
    """Base parsed guard-expression node."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class LiteralNode(GuardExpressionNode):
    value: object


@dataclass(frozen=True, slots=True)
class ReferenceNode(GuardExpressionNode):
    parts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ListNode(GuardExpressionNode):
    items: tuple[GuardExpressionNode, ...] = ()


@dataclass(frozen=True, slots=True)
class CallArgumentNode(GuardExpressionNode):
    name: str
    value: GuardExpressionNode


@dataclass(frozen=True, slots=True)
class CallNode(GuardExpressionNode):
    target: ReferenceNode
    arguments: tuple[CallArgumentNode, ...] = ()
    fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UnaryNode(GuardExpressionNode):
    operator: Literal["not"]
    operand: GuardExpressionNode


@dataclass(frozen=True, slots=True)
class BinaryNode(GuardExpressionNode):
    operator: ExpressionOperator
    left: GuardExpressionNode
    right: GuardExpressionNode


@dataclass(frozen=True, slots=True)
class ParsedGuardExpression:
    """Structured parsed representation of a string-form guard expression."""

    source: str
    root: GuardExpressionNode


@dataclass(frozen=True, slots=True)
class GuardExpressionParseError(Exception):
    """Structured parser error suitable for workflow diagnostics."""

    message: str
    position: int
    end: int | None = None

    def to_diagnostic(self, *, path: tuple[str, ...], source: str, expression: str) -> Diagnostic:
        snippet = expression[self.position : self.end if self.end is not None else self.position + 1]
        return Diagnostic(
            code="validation.workflow.guard_expr.syntax",
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
class _Token:
    kind: str
    text: str
    start: int
    end: int


def parse_guard_expression(expression: str) -> ParsedGuardExpression:
    """Parse a string-form guard expression into a structured tree."""

    parser = _Parser(expression)
    root = parser.parse()
    return ParsedGuardExpression(source=expression, root=root)


class _Parser:
    def __init__(self, text: str) -> None:
        self._text = text
        self._tokens = _tokenize(text)
        self._index = 0

    def parse(self) -> GuardExpressionNode:
        node = self._parse_or()
        if self._peek().kind != "EOF":
            token = self._peek()
            raise GuardExpressionParseError("Unexpected trailing token", token.start, token.end)
        return node

    def _parse_or(self) -> GuardExpressionNode:
        node = self._parse_and()
        while self._match_keyword("or") is not None:
            operator = self._previous()
            right = self._parse_and()
            node = BinaryNode(start=node.start, end=right.end, operator="or", left=node, right=right)
        return node

    def _parse_and(self) -> GuardExpressionNode:
        node = self._parse_not()
        while self._match_keyword("and") is not None:
            right = self._parse_not()
            node = BinaryNode(start=node.start, end=right.end, operator="and", left=node, right=right)
        return node

    def _parse_not(self) -> GuardExpressionNode:
        if self._peek_keyword("not") and not self._peek_keyword("not", offset=1, expected_text="in"):
            operator = self._advance()
            operand = self._parse_not()
            return UnaryNode(start=operator.start, end=operand.end, operator="not", operand=operand)
        return self._parse_comparison()

    def _parse_comparison(self) -> GuardExpressionNode:
        node = self._parse_primary()
        if self._match_symbol("==") is not None:
            operator = self._previous()
            right = self._parse_primary()
            return BinaryNode(start=node.start, end=right.end, operator="==", left=node, right=right)
        if self._match_symbol("!=") is not None:
            operator = self._previous()
            right = self._parse_primary()
            return BinaryNode(start=node.start, end=right.end, operator="!=", left=node, right=right)
        if self._peek_keyword("not") and self._peek_keyword("not", offset=1, expected_text="in"):
            start = self._peek().start
            self._advance()
            self._advance()
            right = self._parse_primary()
            return BinaryNode(start=node.start, end=right.end, operator="not in", left=node, right=right)
        if self._match_keyword("in") is not None:
            right = self._parse_primary()
            return BinaryNode(start=node.start, end=right.end, operator="in", left=node, right=right)
        return node

    def _parse_primary(self) -> GuardExpressionNode:
        token = self._peek()
        if token.kind == "LPAREN":
            self._advance()
            node = self._parse_or()
            self._consume("RPAREN", "Expected ')' to close grouped expression")
            return node
        if token.kind == "LBRACKET":
            return self._parse_list()
        if token.kind == "STRING":
            self._advance()
            return LiteralNode(start=token.start, end=token.end, value=_decode_string(token.text, token.start))
        if token.kind == "NUMBER":
            self._advance()
            return LiteralNode(start=token.start, end=token.end, value=_decode_number(token.text))
        if token.kind == "KEYWORD" and token.text in {"true", "false", "null"}:
            self._advance()
            value = {"true": True, "false": False, "null": None}[token.text]
            return LiteralNode(start=token.start, end=token.end, value=value)
        if token.kind == "IDENT":
            return self._parse_reference_or_call()
        raise GuardExpressionParseError("Expected expression term", token.start, token.end)

    def _parse_list(self) -> ListNode:
        start = self._consume("LBRACKET", "Expected '[' to start list literal").start
        items: list[GuardExpressionNode] = []
        if self._peek().kind != "RBRACKET":
            while True:
                items.append(self._parse_or())
                if self._match_symbol(",") is None:
                    break
        end = self._consume("RBRACKET", "Expected ']' to close list literal").end
        return ListNode(start=start, end=end, items=tuple(items))

    def _parse_reference_or_call(self) -> GuardExpressionNode:
        start_token = self._consume("IDENT", "Expected identifier")
        parts = [start_token.text]
        end = start_token.end
        while self._match_symbol(".") is not None:
            next_token = self._peek()
            if next_token.kind != "IDENT":
                raise GuardExpressionParseError("Expected identifier after '.'", next_token.start, next_token.end)
            consumed = self._advance()
            parts.append(consumed.text)
            end = consumed.end

        reference = ReferenceNode(start=start_token.start, end=end, parts=tuple(parts))
        if self._match_symbol("(") is None:
            return reference

        arguments: list[CallArgumentNode] = []
        if self._peek().kind != "RPAREN":
            while True:
                name_token = self._consume("IDENT", "Expected named argument")
                self._consume("EQUAL", "Expected '=' after argument name")
                value = self._parse_or()
                arguments.append(
                    CallArgumentNode(
                        start=name_token.start,
                        end=value.end,
                        name=name_token.text,
                        value=value,
                    )
                )
                if self._match_symbol(",") is None:
                    break
        closing = self._consume("RPAREN", "Expected ')' to close probe call")

        fields: list[str] = []
        end = closing.end
        while self._match_symbol(".") is not None:
            field_token = self._peek()
            if field_token.kind != "IDENT":
                raise GuardExpressionParseError("Expected field name after '.'", field_token.start, field_token.end)
            consumed = self._advance()
            fields.append(consumed.text)
            end = consumed.end
        return CallNode(start=reference.start, end=end, target=reference, arguments=tuple(arguments), fields=tuple(fields))

    def _peek(self, *, offset: int = 0) -> _Token:
        index = self._index + offset
        if index >= len(self._tokens):
            return self._tokens[-1]
        return self._tokens[index]

    def _previous(self) -> _Token:
        return self._tokens[self._index - 1]

    def _advance(self) -> _Token:
        token = self._tokens[self._index]
        self._index += 1
        return token

    def _consume(self, kind: str, message: str) -> _Token:
        token = self._peek()
        if token.kind != kind:
            raise GuardExpressionParseError(message, token.start, token.end)
        return self._advance()

    def _match_keyword(self, text: str) -> _Token | None:
        if self._peek_keyword(text):
            return self._advance()
        return None

    def _peek_keyword(self, text: str, *, offset: int = 0, expected_text: str | None = None) -> bool:
        token = self._peek(offset=offset)
        return token.kind == "KEYWORD" and token.text == (expected_text or text)

    def _match_symbol(self, symbol: str) -> _Token | None:
        token = self._peek()
        symbol_kinds = {
            "(": "LPAREN",
            ")": "RPAREN",
            "[": "LBRACKET",
            "]": "RBRACKET",
            ".": "DOT",
            ",": "COMMA",
            "==": "EQEQ",
            "!=": "NEQ",
            "=": "EQUAL",
        }
        expected_kind = symbol_kinds[symbol]
        if token.kind == expected_kind:
            return self._advance()
        return None


def _tokenize(text: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char == "(":
            tokens.append(_Token("LPAREN", char, index, index + 1))
            index += 1
            continue
        if char == ")":
            tokens.append(_Token("RPAREN", char, index, index + 1))
            index += 1
            continue
        if char == "[":
            tokens.append(_Token("LBRACKET", char, index, index + 1))
            index += 1
            continue
        if char == "]":
            tokens.append(_Token("RBRACKET", char, index, index + 1))
            index += 1
            continue
        if char == ".":
            tokens.append(_Token("DOT", char, index, index + 1))
            index += 1
            continue
        if char == ",":
            tokens.append(_Token("COMMA", char, index, index + 1))
            index += 1
            continue
        if char == "=" and index + 1 < length and text[index + 1] == "=":
            tokens.append(_Token("EQEQ", "==", index, index + 2))
            index += 2
            continue
        if char == "!" and index + 1 < length and text[index + 1] == "=":
            tokens.append(_Token("NEQ", "!=", index, index + 2))
            index += 2
            continue
        if char == "=":
            tokens.append(_Token("EQUAL", char, index, index + 1))
            index += 1
            continue
        if char in {"'", '"'}:
            tokens.append(_read_string(text, index))
            index = tokens[-1].end
            continue
        if char.isdigit() or (char == "-" and index + 1 < length and text[index + 1].isdigit()):
            tokens.append(_read_number(text, index))
            index = tokens[-1].end
            continue
        if char.isalpha() or char == "_":
            token = _read_identifier(text, index)
            tokens.append(token)
            index = token.end
            continue
        raise GuardExpressionParseError(f"Unexpected character '{char}'", index, index + 1)

    tokens.append(_Token("EOF", "", length, length))
    return tuple(tokens)


def _read_identifier(text: str, start: int) -> _Token:
    index = start + 1
    while index < len(text) and (text[index].isalnum() or text[index] == "_"):
        index += 1
    token_text = text[start:index]
    kind = "KEYWORD" if token_text in {"and", "or", "not", "in", "true", "false", "null"} else "IDENT"
    return _Token(kind, token_text, start, index)


def _read_number(text: str, start: int) -> _Token:
    index = start
    if text[index] == "-":
        index += 1
    while index < len(text) and text[index].isdigit():
        index += 1
    if index < len(text) and text[index] == ".":
        index += 1
        if index >= len(text) or not text[index].isdigit():
            raise GuardExpressionParseError("Invalid number literal", start, index)
        while index < len(text) and text[index].isdigit():
            index += 1
    return _Token("NUMBER", text[start:index], start, index)


def _read_string(text: str, start: int) -> _Token:
    quote = text[start]
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return _Token("STRING", text[start : index + 1], start, index + 1)
        index += 1
    raise GuardExpressionParseError("Unterminated string literal", start, len(text))


def _decode_string(text: str, start: int) -> str:
    try:
        return bytes(text[1:-1], "utf-8").decode("unicode_escape")
    except UnicodeDecodeError as exc:
        raise GuardExpressionParseError("Invalid string escape", start, start + len(text)) from exc


def _decode_number(text: str) -> int | float:
    return float(text) if "." in text else int(text)
