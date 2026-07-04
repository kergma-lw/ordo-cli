"""Published workflow contract metadata for machine-readable introspection."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.model.workflow_contract import describe_workflow_contract_data


def describe_workflow_contract() -> JSONObject:
    """Return the published workflow contract surface."""

    return describe_workflow_contract_data()
