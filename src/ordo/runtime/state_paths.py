"""Parsing support for runtime state paths."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic


@dataclass(frozen=True, slots=True)
class ParsedStatePath:
    """Structured parsed representation of a runtime state path."""

    source: str
    state_role: str
    key_expression: str
    fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StatePathParseError(Exception):
    """Structured parser error suitable for workflow diagnostics."""

    message: str
    position: int
    end: int | None = None

    def to_diagnostic(self, *, path: tuple[str, ...], source: str, expression: str) -> Diagnostic:
        snippet = expression[self.position : self.end if self.end is not None else self.position + 1]
        return Diagnostic(
            code="validation.workflow.state_path.syntax",
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


def parse_state_path(expression: str) -> ParsedStatePath:
    """Parse a runtime state path into a structured representation."""

    parser = _Parser(expression)
    return parser.parse()


class _Parser:
    def __init__(self, expression: str) -> None:
        self.expression = expression
        self.length = len(expression)
        self.position = 0

    def parse(self) -> ParsedStatePath:
        self._expect_literal("state")
        self._expect_char(".")
        state_role = self._parse_identifier(allow_hyphen=True, label="state role")
        self._expect_char("[")
        key_expression = self._parse_key_expression()
        fields: list[str] = []
        while self._peek() == ".":
            self.position += 1
            fields.append(self._parse_identifier(label="field name"))
        if self.position != self.length:
            raise StatePathParseError("Unexpected trailing content in state path", self.position, self.length)
        return ParsedStatePath(
            source=self.expression,
            state_role=state_role,
            key_expression=key_expression,
            fields=tuple(fields),
        )

    def _parse_key_expression(self) -> str:
        start = self.position
        depth_paren = 0
        depth_brace = 0
        depth_bracket = 1
        quote: str | None = None
        escaped = False
        while self.position < self.length:
            current = self.expression[self.position]
            if quote is not None:
                self.position += 1
                if escaped:
                    escaped = False
                    continue
                if current == "\\":
                    escaped = True
                    continue
                if current == quote:
                    quote = None
                continue
            if current in {'"', "'"}:
                quote = current
                self.position += 1
                continue
            if current == "(":
                depth_paren += 1
                self.position += 1
                continue
            if current == ")":
                if depth_paren > 0:
                    depth_paren -= 1
                self.position += 1
                continue
            if current == "{":
                depth_brace += 1
                self.position += 1
                continue
            if current == "}":
                if depth_brace > 0:
                    depth_brace -= 1
                self.position += 1
                continue
            if current == "[":
                depth_bracket += 1
                self.position += 1
                continue
            if current == "]":
                depth_bracket -= 1
                if depth_bracket == 0:
                    expression = self.expression[start : self.position].strip()
                    self.position += 1
                    if not expression:
                        raise StatePathParseError("State path key expression must not be empty", start, self.position)
                    return expression
                self.position += 1
                continue
            self.position += 1
        raise StatePathParseError("Expected ']' after state key expression", start, self.length)

    def _parse_identifier(self, *, allow_hyphen: bool = False, label: str) -> str:
        start = self.position
        if start >= self.length:
            raise StatePathParseError(f"Expected {label}", start)
        first = self.expression[self.position]
        if not (first.isalpha() or first == "_"):
            raise StatePathParseError(f"Expected {label}", start, start + 1)
        self.position += 1
        while self.position < self.length:
            current = self.expression[self.position]
            if current.isalnum() or current == "_" or (allow_hyphen and current == "-"):
                self.position += 1
                continue
            break
        return self.expression[start : self.position]

    def _expect_literal(self, text: str) -> None:
        end = self.position + len(text)
        if self.expression[self.position : end] != text:
            raise StatePathParseError(f"Expected '{text}'", self.position, min(end, self.length))
        self.position = end

    def _expect_char(self, char: str) -> None:
        if self._peek() != char:
            raise StatePathParseError(f"Expected '{char}'", self.position, self.position + 1 if self.position < self.length else None)
        self.position += 1

    def _peek(self) -> str | None:
        if self.position >= self.length:
            return None
        return self.expression[self.position]
