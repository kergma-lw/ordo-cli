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
        "authoring_role": "workflow_fragment_reuse",
        "expansion_semantics": "resolve_bind_expand_whole_node_replacement",
        "targets": "files_only",
        "call_fields": [
            {"name": "include", "required": True, "type": "string"},
            {"name": "with", "required": False, "type": "object", "authoring_role": "fragment_argument_bindings"},
        ],
        "fragment_metadata_fields": [
            {"name": "description", "required": False, "type": "string"},
            {"name": "args", "required": False, "type": "object", "authoring_role": "declares_fragment_local_inputs"},
        ],
        "fragment_argument_declaration_forms": [
            {"name": "required_short_form", "shape": "arg_name: string_type_name"},
            {"name": "object_form", "shape": {"type": "string", "required": "boolean_optional", "default": "json_value_optional"}},
        ],
        "fragment_argument_access_surface": "args.name",
        "fragment_argument_default_semantics": {
            "default_makes_argument_optional": True,
            "default_null_is_valid": True,
            "omitted_argument_is_distinct_from_explicit_null_binding": True,
        },
        "state_scope": "global_across_assembled_workflow",
        "step_scope": "local_to_workflow_or_fragment_expansion_scope",
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
        "validation_boundary": "assembled_workflow_after_include_expansion_and_argument_binding",
        "error_codes": [
            "load.workflow.include.not_found",
            "load.workflow.include.cycle",
            "load.workflow.include.depth",
            "load.workflow.include.forbidden_path",
            "load.workflow.include.not_file",
            "load.workflow.include.with.type",
            "load.workflow.include.args.invalid_declaration",
            "load.workflow.include.args.missing",
            "load.workflow.include.args.unknown",
            "load.workflow.include.args.type",
        ],
    },
    "run_contract": {
        "directive_field": "run",
        "authoring_role": "workflow_fragment_invocation",
        "execution_semantics": "runtime_scoped_fragment_invocation",
        "call_fields": [
            {"name": "run", "required": True, "type": "string"},
            {"name": "if", "required": False, "type": "string", "authoring_role": "caller_scoped_invocation_condition"},
            {"name": "with", "required": False, "type": "object", "authoring_role": "fragment_argument_bindings"},
        ],
        "fragment_argument_access_surface": "args.name",
        "caller_scoped_condition_surface": ["inputs", "state", "step"],
        "caller_scoped_binding_surface": ["inputs", "state", "step"],
    },
    "block_forms": [
        {"name": "guard_block", "required_fields": ["guards"], "optional_fields": []},
        {"name": "step_block", "required_fields": ["steps"], "optional_fields": []},
        {"name": "include_block", "required_fields": ["include"], "optional_fields": ["with"]},
        {"name": "run_block", "required_fields": ["run"], "optional_fields": ["if", "with"]},
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
            "allowed_roots": ["inputs", "args", "state", "step"],
            "allowed_builtins": ["format"],
            "allowed_filters": ["lower", "trim", "slug", "eq", "ne", "not"],
            "boolean_operators": ["and", "or", "not", "parentheses"],
        },
    },
}


def describe_workflow_contract_data() -> JSONObject:
    """Return a defensive copy of canonical workflow contract metadata."""

    return deepcopy(WORKFLOW_CONTRACT)
