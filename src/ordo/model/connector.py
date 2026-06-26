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


@dataclass(frozen=True, slots=True)
class Connector:
    """Public connector family and its stable operation registry surface."""

    namespace: str
    bootstrap: ConnectorBootstrap = field(default_factory=ConnectorBootstrap)
    operations: tuple[OperationContract, ...] = ()
