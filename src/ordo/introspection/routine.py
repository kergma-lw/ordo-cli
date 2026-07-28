"""Published routine contract metadata for machine-readable introspection."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.model.routine_contract import describe_routine_contract_data


def describe_routine_contract() -> JSONObject:
    """Return the published routine-registry contract surface."""

    return describe_routine_contract_data()
