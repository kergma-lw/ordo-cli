"""Root discovery surface for machine-readable introspection."""

from __future__ import annotations

from ordo.model.json import JSONObject

from .capabilities import describe_capabilities
from .envelope import build_introspection_envelope
from .operations import describe_operations
from .playbook import describe_playbook_contract
from .workflow import describe_workflow_contract


def describe_system() -> JSONObject:
    """Return the root introspection surface for zero-knowledge discovery."""

    capabilities = describe_capabilities()
    operations = describe_operations()
    playbook_contract = describe_playbook_contract()
    workflow_contract = describe_workflow_contract()
    return build_introspection_envelope(
        sections={
            "discovery": {
                "entrypoint": "describe_system",
                "sections": {
                    "capabilities": {
                        "producer": "describe_capabilities",
                        "published": True,
                    },
                    "operations": {
                        "producer": "describe_operations",
                        "published": True,
                    },
                    "playbook_contract": {
                        "producer": "describe_playbook_contract",
                        "published": True,
                    },
                    "workflow_contract": {
                        "producer": "describe_workflow_contract",
                        "published": True,
                    }
                },
            },
            "capabilities": capabilities,
            "operations": operations,
            "playbook_contract": playbook_contract,
            "workflow_contract": workflow_contract,
        }
    )
