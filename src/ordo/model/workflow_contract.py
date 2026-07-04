"""Canonical contract metadata for workflow authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

WORKFLOW_CONTRACT: JSONObject = {
    "document_kind": "workflow",
    "version": 0,
    "top_level_fields": [
        {"name": "version", "required": True, "type": "integer"},
        {"name": "workflow", "required": True, "type": "string"},
        {"name": "inputs", "required": False, "type": "object"},
        {"name": "state_needs", "required": False, "type": "object"},
        {"name": "guards", "required": True, "type": "array"},
        {"name": "steps", "required": True, "type": "array"},
    ],
    "guard_forms": [
        {"name": "operation_call", "shape": {"uses": "string", "with": "object"}},
        {"name": "expression", "shape": "string"},
    ],
    "step_forms": [
        {
            "name": "operation_call",
            "required_fields": ["name", "uses"],
            "optional_fields": ["with"],
        },
        {
            "name": "state_set",
            "required_fields": ["name", "state_set"],
            "optional_fields": [],
        },
        {
            "name": "state_delete",
            "required_fields": ["name", "state_delete"],
            "optional_fields": [],
        },
    ],
}


def describe_workflow_contract_data() -> JSONObject:
    """Return a defensive copy of canonical workflow contract metadata."""

    return deepcopy(WORKFLOW_CONTRACT)
