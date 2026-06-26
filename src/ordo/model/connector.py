"""Public connector contract models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .json import JSONObject

OperationKind = Literal["probe", "action"]


@dataclass(frozen=True, slots=True)
class ConnectorBootstrap:
    """Shared family-level prerequisites and context surface."""

    prerequisites: tuple[str, ...] = ()
    context_fields: tuple[str, ...] = ()

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped bootstrap contract."""

        return {
            "prerequisites": list(self.prerequisites),
            "context_fields": list(self.context_fields),
        }


@dataclass(frozen=True, slots=True)
class OperationContract:
    """Public operation contract surface, independent of implementation internals."""

    name: str
    kind: OperationKind
    inputs: JSONObject = field(default_factory=dict)
    prerequisites: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    outputs: JSONObject = field(default_factory=dict)
    failure_modes: tuple[str, ...] = ()

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped operation contract."""

        return {
            "name": self.name,
            "kind": self.kind,
            "inputs": dict(self.inputs),
            "prerequisites": list(self.prerequisites),
            "effects": list(self.effects),
            "outputs": dict(self.outputs),
            "failure_modes": list(self.failure_modes),
        }


@dataclass(frozen=True, slots=True)
class Connector:
    """Public connector family and its stable operation registry surface."""

    namespace: str
    bootstrap: ConnectorBootstrap = field(default_factory=ConnectorBootstrap)
    operations: tuple[OperationContract, ...] = ()

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped connector contract."""

        return {
            "namespace": self.namespace,
            "bootstrap": self.bootstrap.to_contract(),
            "operations": [operation.to_contract() for operation in self.operations],
        }
