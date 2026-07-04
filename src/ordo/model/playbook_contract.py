"""Canonical contract metadata for playbook authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

PLAYBOOK_CONTRACT: JSONObject = {
    "document_kind": "playbook",
    "version": 1,
    "discovery": {"path": ".ordo/playbook.yml"},
    "top_level_fields": [
        {"name": "version", "required": True, "type": "integer"},
        {"name": "states", "required": True, "type": "object"},
        {"name": "defaults", "required": False, "type": "object"},
        {"name": "workflows", "required": True, "type": "object"},
        {"name": "profiles", "required": False, "type": "object"},
    ],
    "workflow_entry_fields": [
        {"name": "file", "required": True, "type": "string"},
        {"name": "state_bindings", "required": False, "type": "object"},
    ],
    "profile_entry_fields": [
        {"name": "file", "required": True, "type": "string"},
    ],
    "state_entry_fields": [
        {"name": "path", "required": True, "type": "string"},
    ],
    "defaults_fields": [
        {"name": "profile", "required": False, "type": "string"},
    ],
    "activation_semantics": {
        "discovery": {
            "strategy": "cwd_relative_single_path",
            "path": ".ordo/playbook.yml",
            "missing": "playbook.discovery.missing",
        },
        "workflow_entries": {
            "requires": ["file"],
            "optional": ["state_bindings"],
        },
        "profile_entries": {
            "requires": ["file"],
        },
        "state_entries": {
            "requires": ["path"],
        },
    },
}


def describe_playbook_contract_data() -> JSONObject:
    """Return a defensive copy of canonical playbook contract metadata."""

    return deepcopy(PLAYBOOK_CONTRACT)
