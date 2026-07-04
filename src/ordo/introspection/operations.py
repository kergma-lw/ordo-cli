"""Published operation metadata for machine-readable introspection."""

from __future__ import annotations

from ordo.connectors import get_public_connector_registry
from ordo.model.json import JSONObject


def describe_operations() -> JSONObject:
    """Return the published public operation metadata surface."""

    return get_public_connector_registry().to_contract()
