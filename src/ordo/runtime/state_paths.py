"""Parsing support for runtime state paths."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic


@dataclass(frozen=True, slots=True)
class ParsedStatePath:
    """Structured parsed representation of a runtime state path."""

    source: str
    state_name: str
    key_reference: tuple[str, ...]
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
        self._expect_literal("states")
        self._expect_char(".")
        state_name = self._parse_identifier(allow_hyphen=True, label="state name")
        self._expect_char("[")
        key_reference = self._parse_input_reference()
        self._expect_char("]")
        fields: list[str] = []
        while self._peek() == ".":
            self.position += 1
            fields.append(self._parse_identifier(label="field name"))
        if self.position != self.length:
            raise StatePathParseError("Unexpected trailing content in state path", self.position, self.length)
        return ParsedStatePath(
            source=self.expression,
            state_name=state_name,
            key_reference=key_reference,
            fields=tuple(fields),
        )

    def _parse_input_reference(self) -> tuple[str, ...]:
        start = self.position
        self._expect_literal("inputs")
        parts = ["inputs"]
        while self._peek() == ".":
            self.position += 1
            parts.append(self._parse_identifier(label="input reference segment"))
        if len(parts) == 1:
            raise StatePathParseError("State path input reference must use dotted form such as 'inputs.issue_ref'", start, self.position)
        return tuple(parts)

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
