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
        {"name": "blocks", "required": False, "type": "array"},
    ],
    "block_forms": [
        {"name": "guard_block", "required_fields": ["guards"], "optional_fields": []},
        {"name": "step_block", "required_fields": ["steps"], "optional_fields": []},
    ],
    "guard_forms": [
        {"name": "operation_call", "shape": {"uses": "string", "with": "object"}},
        {"name": "expression", "shape": "string"},
    ],
    "step_form_rules": [
        {
            "name": "exactly_one_step_form",
            "kind": "exclusive_choice",
            "fields": ["uses", "value", "state_set", "state_delete"],
            "message": "A workflow step must define exactly one of uses, value, state_set, or state_delete",
        },
        {
            "name": "with_requires_uses",
            "kind": "dependency",
            "field": "with",
            "requires": ["uses"],
            "message": "The with field is allowed only together with uses",
        },
    ],
    "step_forms": [
        {
            "name": "operation_call",
            "required_fields": ["name", "uses"],
            "optional_fields": ["if", "with", "register"],
        },
        {
            "name": "value",
            "required_fields": ["name", "value"],
            "optional_fields": ["if", "register"],
        },
        {
            "name": "state_set",
            "required_fields": ["name", "state_set"],
            "optional_fields": ["if"],
        },
        {
            "name": "state_delete",
            "required_fields": ["name", "state_delete"],
            "optional_fields": ["if"],
        },
    ],
    "surface_constraints": {
        "guard_expression": {
            "allowed_roots": ["inputs", "probe"],
            "forbidden_features": ["value_expression_filters", "value_expression_builtins", "state_references"],
        },
        "runtime_value_surface": {
            "allowed_roots": ["inputs", "state", "step"],
            "allowed_builtins": ["format"],
            "allowed_filters": ["lower", "trim", "slug", "eq", "ne", "not"],
        },
    },
}


def describe_workflow_contract_data() -> JSONObject:
    """Return a defensive copy of canonical workflow contract metadata."""

    return deepcopy(WORKFLOW_CONTRACT)
