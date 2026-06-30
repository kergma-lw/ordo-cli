"""Public connector registry and built-in connector discovery."""

from __future__ import annotations

from functools import lru_cache

from connectors._family import ActionHandler, ProbeHandler, discover_family_modules
from ordo.model.connector import ConnectorRegistry


@lru_cache(maxsize=1)
def get_public_connector_registry() -> ConnectorRegistry:
    """Return the fixed public v0 connector registry."""

    return ConnectorRegistry(connectors=tuple(module.get_connector() for module in discover_family_modules()))


@lru_cache(maxsize=1)
def get_public_probe_handlers() -> dict[str, ProbeHandler]:
    handlers: dict[str, ProbeHandler] = {}
    for module in discover_family_modules():
        connector = module.get_connector()
        for operation in connector.operations:
            if operation.kind == "probe":
                handler = module.get_probe_handler(operation.name)
                if handler is not None:
                    handlers[f"{connector.namespace}.{operation.name}"] = handler
    return handlers


@lru_cache(maxsize=1)
def get_public_action_handlers() -> dict[str, ActionHandler]:
    handlers: dict[str, ActionHandler] = {}
    for module in discover_family_modules():
        connector = module.get_connector()
        for operation in connector.operations:
            if operation.kind == "action":
                handler = module.get_action_handler(operation.name)
                if handler is not None:
                    handlers[f"{connector.namespace}.{operation.name}"] = handler
    return handlers
