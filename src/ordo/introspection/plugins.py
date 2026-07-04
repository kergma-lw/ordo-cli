"""Published plugin/external connector self-description contract."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.model.plugin_surface_contract import describe_plugin_surface_contract_data


def describe_plugin_surface_contract() -> JSONObject:
    """Return the published self-description boundary for plugin surfaces."""

    return describe_plugin_surface_contract_data()
