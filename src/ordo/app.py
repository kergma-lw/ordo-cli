"""Standard application composition helpers."""

from __future__ import annotations

from ordo.connectors import get_public_connector_provider
from ordo.runtime import ConnectorProvider, set_default_connector_provider


def get_standard_connector_provider() -> ConnectorProvider:
    """Return the standard built-in connector provider for the packaged application."""

    return get_public_connector_provider()


def configure_standard_runtime() -> ConnectorProvider:
    """Configure runtime convenience entry points to use the standard built-in connector provider."""

    provider = get_standard_connector_provider()
    set_default_connector_provider(provider)
    return provider
