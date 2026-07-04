"""Published playbook contract metadata for machine-readable introspection."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.model.playbook_contract import describe_playbook_contract_data


def describe_playbook_contract() -> JSONObject:
    """Return the published playbook contract surface."""

    return describe_playbook_contract_data()
