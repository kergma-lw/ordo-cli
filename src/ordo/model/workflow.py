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
    operation: OperationRef | None = None
    state_set: JSONObject | None = None
    state_delete: str | None = None
    register: str | None = None

    def __post_init__(self) -> None:
        forms = (
            self.operation is not None,
            self.state_set is not None,
            self.state_delete is not None,
        )
        if sum(forms) != 1:
            raise ValueError("Step must define exactly one of operation, state_set, or state_delete")

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped contract form."""

        if self.operation is not None:
            contract = {"name": self.name, **self.operation.to_contract()}
            if self.register is not None:
                contract["register"] = self.register
            return contract
        if self.state_set is not None:
            return {"name": self.name, "state_set": dict(self.state_set)}
        return {"name": self.name, "state_delete": self.state_delete}


@dataclass(frozen=True, slots=True)
class Workflow:
    """Declarative orchestration model loaded from author-facing data."""

    version: int
    workflow: str
    inputs: JSONObject = field(default_factory=dict)
    state_needs: JSONObject = field(default_factory=dict)
    state_bindings: JSONObject = field(default_factory=dict)
    states: JSONObject = field(default_factory=dict)
    step_results: JSONObject = field(default_factory=dict)
    guards: tuple[Guard, ...] = ()
    steps: tuple[Step, ...] = ()

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped workflow contract."""

        return {
            "version": self.version,
            "workflow": self.workflow,
            "inputs": dict(self.inputs),
            "state_needs": dict(self.state_needs),
            "guards": [guard.to_contract() for guard in self.guards],
            "steps": [step.to_contract() for step in self.steps],
        }
