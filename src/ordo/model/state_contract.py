"""Canonical contract metadata for runtime state surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

STATE_CONTRACT: JSONObject = {
    "document_kind": "state_contract",
    "workflow_surface": {
        "state_needs_field": "state_needs",
        "state_binding_field": "state_bindings",
        "storage_targets_field": "states",
        "step_state_set_field": "state_set",
        "step_state_delete_field": "state_delete",
    },
    "path_forms": {
        "root": "state",
        "shape": "state.<role>[inputs.<key>][.<field>...]",
        "root_reference": "inputs",
        "supports_nested_fields": True,
        "supports_hyphenated_roles": True,
    },
    "invalid_path_rules": [
        {
            "name": "root_must_be_state",
            "message": "state path must start with 'state'",
        },
        {
            "name": "key_reference_must_use_dotted_inputs",
            "message": "state path key reference must use dotted inputs form such as 'inputs.task_key'",
        },
        {
            "name": "no_trailing_content",
            "message": "state path must not contain trailing content",
        },
    ],
    "storage_document": {
        "version": 1,
        "required_fields": ["version", "values"],
        "values_type": "object",
    },
    "runtime_rules": [
        {
            "name": "bound_role_required",
            "message": "state role must be bound before runtime access",
            "error_code": "runtime.state.binding_missing",
        },
        {
            "name": "scalar_key_required",
            "message": "state key reference must resolve to a scalar value",
            "error_code": "runtime.state.key_invalid",
        },
        {
            "name": "declared_location_required",
            "message": "undeclared state locations are runtime errors",
            "error_code": "runtime.state.declaration_missing",
        },
    ],
}


def describe_state_contract_data() -> JSONObject:
    """Return a defensive copy of canonical state contract metadata."""

    return deepcopy(STATE_CONTRACT)
