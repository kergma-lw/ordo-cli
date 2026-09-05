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
    "preflight": {
        "classification": "effectful",
        "top_level_status": "deferred",
        "rule": "Check conditions and gates first, then defer eligible top-level mutations without mutation, simulation, outputs, registers, or reusable observations; continue to independent guards.",
        "planning": "Retain ordered nodes with reuse_policy not_reusable and planned_probe_result null; execute admitted mutations once in order, with divergence_status not_applicable for deferred nodes.",
        "boundary": "Nested analysis does not defer mutations. A reached run or loop after deferral halts with state_deferral_invocation_barrier; profile switches cannot resume that barrier.",
        "verification_scope": "Validate individual workflows and children, not flattened caller-child access streams. Cross-invocation and cross-iteration guarantees remain deferred; this is not a full composed-run or cross-run proof.",
    },
    "runtime_rules": [
        {
            "name": "write_after_last_read",
            "message": "Before binding, authoring validation requires writes or deletes of a logical state role only after its final read, regardless of key or field. Bound validation instead compares actual storage in each access context. Use step registers for per-run dataflow.",
            "error_code": "validation.workflow.state_role.write_before_last_read",
        },
        {
            "name": "bound_storage_write_after_last_read",
            "message": "After binding, write or delete only after the final read of the same actual file, regardless of role, state name, profile, key, or field. Resolve relative paths in each access context; normalized paths, symlinks, and existing hardlinks can alias. The same role may access different files and be valid.",
            "error_code": "validation.workflow.state_storage.write_before_last_read",
        },
        {
            "name": "relevant_storage_identity_required",
            "message": "Conservatively reject early only relevant write/later-read pairs whose storage identity cannot be established without execution or observations. This is not a proven ordering violation; uncertain context alone does not reject read-only, read-before-write, or known-disjoint access. Cross-invocation and cross-iteration guarantees remain deferred, without a new loop mutation ban.",
            "error_code": "validation.workflow.state_storage.identity_unresolved",
        },
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
