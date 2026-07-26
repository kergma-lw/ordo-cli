"""Public connector contract models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .json import JSONObject, JSONValue

OperationKind = Literal["probe", "action"]
_PLACEHOLDER_PATTERN = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")


@dataclass(frozen=True, slots=True)
class PreflightObservation:
    """Canonical structured recommended probe observation template."""

    probe: str
    with_: JSONObject = field(default_factory=dict)
    fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.probe, str) or not self.probe or "." not in self.probe:
            raise ValueError("preflight observation probe must be a non-empty dotted public reference")
        for name, value in self.with_.items():
            if not isinstance(name, str) or not name:
                raise ValueError("preflight observation argument names must be non-empty strings")
            if not _is_json_value(value):
                raise ValueError("preflight observation argument values must be valid JSON-shaped scalar, list, or object values")
        for field_name in self.fields:
            if not isinstance(field_name, str) or not field_name:
                raise ValueError("preflight observation fields must be non-empty strings")

    def placeholder_names(self) -> tuple[str, ...]:
        names: list[str] = []
        for value in self.with_.values():
            match = _PLACEHOLDER_PATTERN.fullmatch(value)
            if match is not None:
                names.append(match.group(1))
        return tuple(names)

    def to_contract(self) -> JSONObject:
        payload: JSONObject = {
            "probe": self.probe,
            "with": dict(self.with_),
        }
        if self.fields:
            payload["fields"] = list(self.fields)
        return payload


def _is_json_value(value: JSONValue) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False


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
    preflight_observations: tuple[PreflightObservation, ...] = ()

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
            "preflight_observations": [item.to_contract() for item in self.preflight_observations],
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
