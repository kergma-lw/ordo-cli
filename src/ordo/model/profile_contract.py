"""Canonical contract metadata for profile authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

PROFILE_CONTRACT: JSONObject = {
    "document_kind": "profile",
    "top_level_fields": [
        {"name": "name", "required": True, "type": "string"},
        {"name": "inputs", "required": False, "type": "object", "runtime_effect": "applies_missing_workflow_inputs"},
        {"name": "checks", "required": False, "type": "array", "runtime_effect": "published_metadata_only"},
        {"name": "overrides", "required": False, "type": "array", "runtime_effect": "published_metadata_only"},
    ],
    "override_fields": [
        {"name": "target", "required": True, "type": "string"},
        {"name": "with", "required": False, "type": "object"},
        {"name": "reason", "required": False, "type": "string"},
    ],
    "compose_semantics": {
        "inputs": {
            "strategy": "first_writer_wins",
            "conflict": "validation_error",
        },
        "checks": {
            "strategy": "deduplicated_union",
            "order": "left_to_right",
        },
        "overrides": {
            "conflict_key": "target",
            "conflict": "validation_error",
        },
    },
    "workflow_apply_semantics": {
        "inputs": {
            "may_add_missing": True,
            "may_override_explicit_workflow_values": False,
            "conflict": "validation_error",
        },
        "checks": {
            "mutates_workflow_contract": False,
        },
        "overrides": {
            "mutates_workflow_steps": False,
            "published_as_explicit_metadata": True,
        },
    },
}


def describe_profile_contract_data() -> JSONObject:
    """Return a defensive copy of canonical profile contract metadata."""

    return deepcopy(PROFILE_CONTRACT)
