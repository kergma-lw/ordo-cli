"""Canonical contract metadata for project-local routine registries."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

ROUTINE_CONTRACT: JSONObject = {
    "document_kind": "routine_registry",
    "version": 1,
    "discovery": {"path": ".ordo/routines.yaml"},
    "top_level_fields": [
        {"name": "version", "required": True, "type": "integer"},
        {"name": "routines", "required": True, "type": "object"},
    ],
    "routine_entry_fields": [
        {"name": "kind", "required": True, "type": "string"},
        {"name": "summary", "required": True, "type": "string"},
        {"name": "args", "required": False, "type": "object"},
        {"name": "implementation", "required": True, "type": "object"},
        {"name": "failure_modes", "required": True, "type": "array"},
        {"name": "outputs", "required": False, "type": "object"},
        {"name": "log_hints", "required": False, "type": "object"},
    ],
    "implementation_fields": [
        {"name": "argv", "required": True, "type": "array"},
    ],
}


def describe_routine_contract_data() -> JSONObject:
    """Return a defensive copy of canonical routine-registry contract metadata."""

    return deepcopy(ROUTINE_CONTRACT)
