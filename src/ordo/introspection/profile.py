"""Published profile contract metadata for machine-readable introspection."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.model.profile_contract import describe_profile_contract_data


def describe_profile_contract() -> JSONObject:
    """Return the published profile contract surface."""

    return describe_profile_contract_data()
