"""Built-in connector provider composition."""

from __future__ import annotations

from functools import lru_cache

from ordo.runtime.providers import ConnectorProvider

from .operations import evaluate_probe, execute_operation
from .registry import get_public_connector_registry


@lru_cache(maxsize=1)
def get_public_connector_provider() -> ConnectorProvider:
    """Return the built-in connector provider used by package-level convenience APIs."""

    return ConnectorProvider(
        registry=get_public_connector_registry(),
        guard_probe=evaluate_probe,
        step_executor=execute_operation,
    )
