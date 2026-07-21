"""Canonical contract metadata for playbook authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

PLAYBOOK_CONTRACT: JSONObject = {
    "document_kind": "playbook",
    "version": 1,
    "discovery": {"path": ".ordo/ordo.yaml"},
    "top_level_fields": [
        {"name": "version", "required": True, "type": "integer"},
        {"name": "pre_run", "required": False, "type": "array"},
        {"name": "states", "required": True, "type": "object"},
        {"name": "defaults", "required": False, "type": "object"},
        {"name": "workflows", "required": True, "type": "object"},
        {"name": "profiles", "required": False, "type": "object"},
    ],
    "workflow_entry_fields": [
        {"name": "file", "required": True, "type": "string"},
        {
            "name": "description",
            "required": False,
            "type": "string",
            "documentation_role": "project_local_workflow_summary",
        },
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
    "pre_run_entry_fields": [
        {"name": "file", "required": True, "type": "string"},
        {
            "name": "state_bindings",
            "required": False,
            "type": "object",
            "documentation_role": "playbook_owned_pre_run_state_bindings",
        },
    ],
    "state_entry_fields": [
        {"name": "path", "required": True, "type": "string"},
    ],
    "defaults_fields": [
        {"name": "profile", "required": False, "type": "string", "runtime_effect": "selects_active_profile"},
        {
            "name": "working_directory",
            "required": False,
            "type": "string",
            "runtime_effect": "sets_default_execution_working_directory",
            "resolution_base": "playbook_dir",
            "expression_syntax": "${...}",
            "expression_surface": "activation_input_value_expression",
            "expression_allowed_roots": ["inputs"],
            "expression_forbidden_roots": ["state", "step"],
        },
    ],
    "activation_semantics": {
        "discovery": {
            "strategy": "cwd_relative_single_path",
            "path": ".ordo/ordo.yaml",
            "missing": "playbook.discovery.missing",
        },
        "workflow_entries": {
            "requires": ["file"],
            "optional": ["description", "working_directory", "state_bindings"],
        },
        "pre_run": {
            "item_type": "pre_run_entry",
            "requires": ["file"],
            "optional": ["state_bindings"],
            "effect": "executes_before_requested_workflow_in_same_runtime_session",
            "launch_context_boundary": "playbook_owned",
            "state_dependency_boundary": "must_not_widen_main_workflow_state_contract",
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
