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
        {
            "name": "working_directory",
            "required": False,
            "type": "string",
            "runtime_effect": "sets_execution_working_directory",
            "resolution_base": "playbook_dir",
            "expression_syntax": "${...}",
            "expression_surface": "activation_input_value_expression",
            "expression_allowed_roots": ["inputs"],
            "expression_forbidden_roots": ["state", "step"],
        },
        {"name": "state_bindings", "required": False, "type": "object"},
    ],
    "profile_entry_fields": [
        {"name": "file", "required": True, "type": "string"},
    ],
    "state_entry_fields": [
        {"name": "path", "required": True, "type": "string"},
    ],
    "defaults_fields": [
        {"name": "profile", "required": False, "type": "string", "runtime_effect": "selects_active_profile"},
    ],
    "activation_semantics": {
        "discovery": {
            "strategy": "cwd_relative_single_path",
            "path": ".ordo/playbook.yml",
            "missing": "playbook.discovery.missing",
        },
        "workflow_entries": {
            "requires": ["file"],
            "optional": ["working_directory", "state_bindings"],
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
