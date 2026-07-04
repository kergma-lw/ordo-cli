"""Shared machine-readable envelope for published introspection surfaces."""

from __future__ import annotations

from collections.abc import Mapping

from ordo.model.json import JSONObject, JSONValue

INTROSPECTION_VERSION = 1


def build_introspection_envelope(*, sections: Mapping[str, JSONValue] | None = None) -> JSONObject:
    """Return the shared versioned envelope for introspection output."""

    return {
        "introspection_version": INTROSPECTION_VERSION,
        "sections": {} if sections is None else dict(sections),
    }
