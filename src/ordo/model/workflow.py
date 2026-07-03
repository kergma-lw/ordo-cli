"""Workflow orchestration models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .json import JSONObject, JSONValue


@dataclass(frozen=True, slots=True)
class OperationRef:
    """Stable reference to a public connector operation."""

    uses: str
    with_: JSONObject = field(default_factory=dict, kw_only=True)

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped contract form."""

        return {"uses": self.uses, "with": dict(self.with_)}


@dataclass(frozen=True, slots=True)
class Guard:
    """Pre-execution check with no intended side effects."""

    operation: OperationRef | None = None
    expr: str | None = None

    def __post_init__(self) -> None:
        has_operation = self.operation is not None
        has_expr = self.expr is not None
        if has_operation == has_expr:
            raise ValueError("Guard must define exactly one of operation or expr")

    @property
    def reference(self) -> str:
        if self.operation is not None:
            return self.operation.uses
        return self.expr or "<unknown-guard>"

    def to_contract(self) -> JSONValue:
        """Return the stable JSON-shaped contract form."""

        if self.operation is not None:
            return self.operation.to_contract()
        return self.expr


@dataclass(frozen=True, slots=True)
class Step:
    """Ordered effectful workflow step."""

    name: str
    operation: OperationRef

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped contract form."""

        return {"name": self.name, **self.operation.to_contract()}


@dataclass(frozen=True, slots=True)
class Workflow:
    """Declarative orchestration model loaded from author-facing data."""

    version: int
    workflow: str
    inputs: JSONObject = field(default_factory=dict)
    states: JSONObject = field(default_factory=dict)
    guards: tuple[Guard, ...] = ()
    steps: tuple[Step, ...] = ()

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped workflow contract."""

        return {
            "version": self.version,
            "workflow": self.workflow,
            "inputs": dict(self.inputs),
            "states": dict(self.states),
            "guards": [guard.to_contract() for guard in self.guards],
            "steps": [step.to_contract() for step in self.steps],
        }
