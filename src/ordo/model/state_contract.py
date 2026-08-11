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
        "shape": "state.<role>[<expression>][.<field>...]",
        "key_expression_surface": "embedded_value_expression",
        "supports_nested_fields": True,
        "supports_hyphenated_roles": True,
    },
    "invalid_path_rules": [
        {
            "name": "root_must_be_state",
            "message": "state path must start with 'state'",
        },
        {
            "name": "key_expression_must_be_valid_local_expression",
            "message": "state path key expression must be a valid local expression",
        },
        {
            "name": "no_trailing_content",
            "message": "state path must not contain trailing content",
        },
    ],
    "storage_document": {
        "root_type": "object",
        "top_level_keys": "user-defined",
    },
    "runtime_rules": [
        {
            "name": "bound_role_required",
            "message": "state role must be bound before runtime access",
            "error_code": "runtime.state.binding_missing",
        },
        {
            "name": "non_null_scalar_key_required",
            "message": "state key expression must resolve to a non-null scalar value",
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
