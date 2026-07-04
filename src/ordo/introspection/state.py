"""Published state contract metadata for machine-readable introspection."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.model.state_contract import describe_state_contract_data


def describe_state_contract() -> JSONObject:
    """Return the published state contract surface."""

    return describe_state_contract_data()
