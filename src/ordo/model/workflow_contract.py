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
        {
            "name": "inputs",
            "required": False,
            "type": "object",
            "authoring_role": "declares_global_activation_inputs",
            "activation_requirement": "all_declared_keys_required",
            "unknown_input_policy": "reject_unknown_inputs",
        },
        {"name": "state_needs", "required": False, "type": "object"},
        {"name": "blocks", "required": False, "type": "array"},
    ],
    "inputs_contract": {
        "scope": "global",
        "access_surface": "inputs.name",
        "declaration_shape": "mapping",
        "declared_keys_required_at_activation": True,
        "rejects_unknown_activation_inputs": True,
        "empty_string_is_distinct_value": True,
        "null_is_distinct_from_missing": True,
        "validated_by": "runtime",
    },
    "include_contract": {
        "directive_field": "include",
        "expansion_semantics": "whole_node_replacement",
        "targets": "files_only",
        "search_order": [
            "including_file_dir",
            "launch_dir",
            "launch_dir_dot_ordo",
            "home_dot_ordo",
            "built_in_includes_dir",
        ],
        "extension_probe_order": [".yaml", ".yml"],
        "stops_on_first_match": True,
        "cycle_detection": "current_expansion_stack",
        "max_depth": 32,
        "validation_boundary": "assembled_workflow_after_include_expansion",
        "error_codes": [
            "load.workflow.include.not_found",
            "load.workflow.include.cycle",
            "load.workflow.include.depth",
            "load.workflow.include.forbidden_path",
            "load.workflow.include.not_file",
        ],
    },
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
            "optional_fields": ["if", "with", "register", "launcher"],
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
            "boolean_operators": ["and", "or", "not", "parentheses"],
            "forbidden_features": ["value_expression_filters", "value_expression_builtins", "state_references"],
        },
        "runtime_value_surface": {
            "allowed_roots": ["inputs", "state", "step"],
            "allowed_builtins": ["format"],
            "allowed_filters": ["lower", "trim", "slug", "eq", "ne", "not"],
            "boolean_operators": ["and", "or", "not", "parentheses"],
        },
    },
}


def describe_workflow_contract_data() -> JSONObject:
    """Return a defensive copy of canonical workflow contract metadata."""

    return deepcopy(WORKFLOW_CONTRACT)
