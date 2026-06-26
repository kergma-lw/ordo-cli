"""Workflow orchestration models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .json import JSONObject


@dataclass(frozen=True, slots=True)
class OperationRef:
    """Stable reference to a public connector operation."""

    uses: str
    with_: JSONObject = field(default_factory=dict, kw_only=True)


@dataclass(frozen=True, slots=True)
class Guard:
    """Pre-execution check with no intended side effects."""

    operation: OperationRef


@dataclass(frozen=True, slots=True)
class Step:
    """Ordered effectful workflow step."""

    name: str
    operation: OperationRef


@dataclass(frozen=True, slots=True)
class Workflow:
    """Declarative orchestration model loaded from author-facing data."""

    version: int
    workflow: str
    inputs: JSONObject = field(default_factory=dict)
    guards: tuple[Guard, ...] = ()
    steps: tuple[Step, ...] = ()
