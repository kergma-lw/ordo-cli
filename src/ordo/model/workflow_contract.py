"""Canonical contract metadata for workflow authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject
from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS


_PUBLISHED_FILTERS = list(VALUE_EXPRESSION_FILTERS)
_PUBLISHED_BUILTINS = list(VALUE_EXPRESSION_BUILTINS)

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
        {
            "name": "let",
            "required": False,
            "type": "object",
            "authoring_role": "declares_workflow_local_named_expressions",
        },
        {"name": "state_needs", "required": False, "type": "object"},
        {"name": "blocks", "required": False, "type": "array"},
    ],
    "inputs_contract": {
        "scope": "global",
        "access_surface": "inputs.name",
        "declaration_shape": "mapping",
        "declaration_fields": [
            {"name": "description", "required": False, "type": "string", "authoring_role": "input_meaning"},
            {"name": "hint", "required": False, "type": "string", "authoring_role": "input_guidance", "validation_effect": "none"},
        ],
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
        "surface_kind": "step_form",
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
    ],
    "guard_forms": [
        {"name": "operation_call", "shape": {"uses": "string", "with": "object"}, "status": "compatibility_only"},
        {"name": "expression", "shape": "string", "status": "stable_preferred"},
    ],
    "step_form_rules": [
        {
            "name": "exactly_one_step_form",
            "kind": "exclusive_choice",
            "fields": ["uses", "run", "profile_switch", "value", "result", "publish", "state_set", "state_delete"],
            "message": "A workflow step must define exactly one of uses, run, profile_switch, value, result, publish, state_set, or state_delete",
        },
        {
            "name": "with_requires_uses",
            "kind": "dependency",
            "field": "with",
            "requires": ["uses", "run"],
            "message": "The with field is allowed only together with uses or run",
        },
    ],
    "step_forms": [
        {
            "name": "operation_call",
            "required_fields": ["name", "uses"],
            "optional_fields": ["if", "with", "register", "launcher"],
            "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
            "deprecated_optional_fields": ["launcher"],
            "preferred_alternatives": {"launcher": "routine_or_profile_context"},
        },
        {
            "name": "run_invocation",
            "required_fields": ["name", "run"],
            "optional_fields": ["if", "with", "for_each", "register"],
            "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        },
        {
            "name": "profile_switch",
            "required_fields": ["name", "profile_switch"],
            "optional_fields": ["if"],
            "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        },
        {
            "name": "value",
            "required_fields": ["name", "value"],
            "optional_fields": ["if", "register"],
            "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        },
        {
            "name": "result",
            "required_fields": ["name", "result"],
            "optional_fields": ["if"],
            "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        },
        {
            "name": "publish",
            "required_fields": ["name", "publish"],
            "optional_fields": ["if"],
            "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        },
        {
            "name": "state_set",
            "required_fields": ["name", "state_set"],
            "optional_fields": ["if"],
            "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        },
        {
            "name": "state_delete",
            "required_fields": ["name", "state_delete"],
            "optional_fields": ["if"],
            "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        },
    ],
    "surface_constraints": {
        "guard_expression": {
            "allowed_roots": ["inputs", "probe", "state"],
            "allowed_filters": list(_PUBLISHED_FILTERS),
            "allowed_builtins": list(_PUBLISHED_BUILTINS),
            "boolean_operators": ["and", "or", "not", "parentheses"],
            "representation_adapter_policy": {
                "read_only_allowed": True,
                "write_paths_forbidden": True,
                "forbidden_write_surface": "->...",
            },
            "result_contract": {
                "required_output_type": "boolean",
                "non_boolean_result": "error",
            },
        },
        "runtime_value_surface": {
            "allowed_roots": ["inputs", "args", "state", "step"],
            "allowed_builtins": list(_PUBLISHED_BUILTINS),
            "allowed_filters": list(_PUBLISHED_FILTERS),
            "boolean_operators": ["and", "or", "not", "parentheses"],
        },
    },
}


def describe_workflow_contract_data() -> JSONObject:
    """Return a defensive copy of canonical workflow contract metadata."""

    return deepcopy(WORKFLOW_CONTRACT)
