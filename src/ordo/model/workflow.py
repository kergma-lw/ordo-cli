"""Workflow orchestration models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .json import JSONObject


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

    operation: OperationRef

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped contract form."""

        return self.operation.to_contract()


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
    guards: tuple[Guard, ...] = ()
    steps: tuple[Step, ...] = ()

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped workflow contract."""

        return {
            "version": self.version,
            "workflow": self.workflow,
            "inputs": dict(self.inputs),
            "guards": [guard.to_contract() for guard in self.guards],
            "steps": [step.to_contract() for step in self.steps],
        }
