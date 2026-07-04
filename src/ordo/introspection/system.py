"""Root discovery surface for machine-readable introspection."""

from __future__ import annotations

from ordo.model.json import JSONObject

from .envelope import build_introspection_envelope
from .registry import PUBLISHED_INTROSPECTION_SECTIONS, describe_published_sections
from .workflow import describe_workflow_contract


def describe_system() -> JSONObject:
    """Return the root introspection surface for zero-knowledge discovery."""

    published_sections = describe_published_sections()
    return build_introspection_envelope(
        sections={
            "discovery": {
                "entrypoint": "describe_system",
                "sections": {section.name: {"producer": section.producer_name, "published": True} for section in PUBLISHED_INTROSPECTION_SECTIONS},
            },
            **published_sections,
        }
    )
