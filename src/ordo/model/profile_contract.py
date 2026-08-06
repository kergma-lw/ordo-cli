"""Canonical contract metadata for profile authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

PROFILE_CONTRACT: JSONObject = {
    "document_kind": "profile",
    "top_level_fields": [
        {"name": "name", "required": True, "type": "string"},
        {"name": "inputs", "required": False, "type": "object", "runtime_effect": "applies_missing_workflow_inputs"},
        {
            "name": "working_directory",
            "required": False,
            "type": "string",
            "runtime_effect": "sets_profile_execution_working_directory",
            "resolution_base": "playbook_dir",
            "expression_syntax": "${...}",
            "expression_surface": "activation_input_value_expression",
            "expression_allowed_roots": ["inputs"],
            "expression_forbidden_roots": ["state", "step"],
        },
        {"name": "connectors", "required": False, "type": "object", "runtime_effect": "supplies_raw_connector_bootstrap_input"},
        {"name": "checks", "required": False, "type": "array", "runtime_effect": "published_metadata_only"},
        {"name": "overrides", "required": False, "type": "array", "runtime_effect": "published_metadata_only"},
        {"name": "launchers", "required": False, "type": "object", "runtime_effect": "publishes_profile_scoped_launchers", "status": "deprecated", "preferred_alternative": "published_routines"},
    ],
    "override_fields": [
        {"name": "target", "required": True, "type": "string"},
        {"name": "with", "required": False, "type": "object"},
        {"name": "reason", "required": False, "type": "string"},
    ],
    "launcher_fields": [
        {"name": "file", "required": False, "type": "string"},
        {"name": "connector", "required": False, "type": "string"},
        {"name": "before", "required": False, "type": "string"},
        {"name": "after", "required": False, "type": "string"},
    ],
    "compose_semantics": {
        "inputs": {
            "strategy": "first_writer_wins",
            "conflict": "validation_error",
        },
        "working_directory": {
            "strategy": "first_writer_wins",
            "conflict": "validation_error",
        },
        "connectors": {
            "strategy": "shallow_merge_by_family",
            "conflict": "validation_error",
            "conflict_key": "family_field",
        },
        "checks": {
            "strategy": "deduplicated_union",
            "order": "left_to_right",
        },
        "overrides": {
            "conflict_key": "target",
            "conflict": "validation_error",
        },
        "launchers": {
            "strategy": "first_writer_wins",
            "conflict": "validation_error",
            "conflict_key": "launcher_name",
            "status": "deprecated",
        },
    },
    "workflow_apply_semantics": {
        "inputs": {
            "may_add_missing": True,
            "may_override_explicit_workflow_values": False,
            "conflict": "validation_error",
        },
        "working_directory": {
            "mutates_workflow_steps": False,
            "published_as_explicit_metadata": True,
        },
        "connectors": {
            "mutates_workflow_steps": False,
            "published_as_explicit_metadata": False,
            "consumer": "connector_bootstrap",
        },
        "checks": {
            "mutates_workflow_contract": False,
        },
        "overrides": {
            "mutates_workflow_steps": False,
            "published_as_explicit_metadata": True,
        },
        "launchers": {
            "mutates_workflow_steps": False,
            "published_as_explicit_metadata": True,
            "status": "deprecated",
        },
    },
}


def describe_profile_contract_data() -> JSONObject:
    """Return a defensive copy of canonical profile contract metadata."""

    return deepcopy(PROFILE_CONTRACT)
