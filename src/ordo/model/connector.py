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
    summary: str | None = None
    inputs: JSONObject = field(default_factory=dict)
    prerequisites: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    outputs: JSONObject = field(default_factory=dict)
    failure_modes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    examples: tuple[JSONObject, ...] = ()
    maturity: str = "stable"
    deprecated: bool = False
    replaced_by: tuple[str, ...] = ()
    invalidates_observations: tuple[str, ...] = ()

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped operation contract."""

        return {
            "name": self.name,
            "kind": self.kind,
            "summary": self.summary,
            "inputs": dict(self.inputs),
            "prerequisites": list(self.prerequisites),
            "effects": list(self.effects),
            "outputs": dict(self.outputs),
            "failure_modes": list(self.failure_modes),
            "tags": list(self.tags),
            "examples": [dict(example) for example in self.examples],
            "maturity": self.maturity,
            "deprecated": self.deprecated,
            "replaced_by": list(self.replaced_by),
            "invalidates_observations": list(self.invalidates_observations),
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


@dataclass(frozen=True, slots=True)
class ConnectorRegistry:
    """Discoverable public registry of stable connector families and operations."""

    connectors: tuple[Connector, ...]

    def list_connectors(self) -> tuple[Connector, ...]:
        return self.connectors

    def get_connector(self, namespace: str) -> Connector | None:
        for connector in self.connectors:
            if connector.namespace == namespace:
                return connector
        return None

    def get_operation(self, reference: str) -> OperationContract | None:
        namespace, separator, operation_name = reference.partition(".")
        if not separator:
            return None

        connector = self.get_connector(namespace)
        if connector is None:
            return None

        for operation in connector.operations:
            if operation.name == operation_name:
                return operation
        return None

    def to_contract(self) -> JSONObject:
        return {"connectors": [connector.to_contract() for connector in self.connectors]}
