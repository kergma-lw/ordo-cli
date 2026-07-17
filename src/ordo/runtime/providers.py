"""Connector-provider abstractions for runtime wiring."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ordo.model.connector import ConnectorRegistry
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow

if TYPE_CHECKING:
    from .resolution import ResolvedConditionExpression, ResolvedExpressionProbe, ResolvedOperation

GuardProbe = Callable[["ResolvedOperation | ResolvedExpressionProbe | ResolvedConditionExpression", Workflow], OperationResult]
StepExecutor = Callable[["ResolvedOperation", Workflow], OperationResult]


@dataclass(frozen=True, slots=True)
class ConnectorProvider:
    """Runtime-facing connector wiring surface."""

    registry: ConnectorRegistry
    guard_probe: GuardProbe
    step_executor: StepExecutor


_default_connector_provider: ConnectorProvider | None = None


def set_default_connector_provider(provider: ConnectorProvider) -> None:
    """Register the process-wide default connector provider used by runtime convenience entry points."""

    global _default_connector_provider
    _default_connector_provider = provider


def clear_default_connector_provider() -> None:
    """Clear the process-wide default connector provider."""

    global _default_connector_provider
    _default_connector_provider = None


def get_default_connector_provider() -> ConnectorProvider:
    """Return the configured default connector provider."""

    if _default_connector_provider is None:
        raise RuntimeError(
            "No default connector provider is configured. "
            "Pass explicit registry/probe/executor wiring or register a provider during composition."
        )
    return _default_connector_provider
