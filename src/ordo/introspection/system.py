"""Root discovery surface for machine-readable introspection."""

from __future__ import annotations

from ordo.model.json import JSONObject

from .capabilities import describe_capabilities
from .envelope import build_introspection_envelope
from .operations import describe_operations


def describe_system() -> JSONObject:
    """Return the root introspection surface for zero-knowledge discovery."""

    capabilities = describe_capabilities()
    operations = describe_operations()
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
                    }
                },
            },
            "capabilities": capabilities,
            "operations": operations,
        }
    )
