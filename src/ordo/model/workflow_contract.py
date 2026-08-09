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
        "step_scope": "shared_across_assembled_workflow_after_include_expansion",
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
        "body_forms": ["named_run_target", "inline_repeated_steps"],
        "call_fields": [
            {"name": "run", "required": True, "type": "string"},
            {"name": "steps", "required": False, "type": "array", "authoring_role": "inline_repeated_body"},
            {
                "name": "if",
                "required": False,
                "type": "condition",
                "authoring_role": "caller_scoped_invocation_condition",
                "surface": "expression_or_structured_condition",
                "structured_operators": ["all", "any", "not"],
                "list_semantics": "implicit_all",
            },
            {
                "name": "gate",
                "required": False,
                "type": "condition",
                "authoring_role": "caller_scoped_step_admission_condition",
                "surface": "expression_or_structured_condition",
                "structured_operators": ["all", "any", "not"],
                "list_semantics": "implicit_all",
                "structured_optional_fields": [
                    {
                        "name": "on_fail",
                        "type": "object",
                        "authoring_role": "gate_failure_diagnostic_context",
                        "value_surface": "step_local_read_only_expression_or_literal",
                        "evaluation_timing": "only_when_gate_verdict_is_failed",
                    }
                ],
            },
            {"name": "with", "required": False, "type": "object", "authoring_role": "fragment_argument_bindings"},
            {"name": "for_each", "required": False, "type": "runtime_value", "authoring_role": "bounded_fan_out_source"},
            {"name": "register", "required": False, "type": "string", "authoring_role": "aggregate_invocation_result"},
        ],
        "fragment_argument_access_surface": "args.name",
        "caller_scoped_condition_surface": ["inputs", "state", "step", "probe"],
        "caller_scoped_binding_surface": ["inputs", "state", "step", "probe"],
        "named_target_scope_boundary": "isolated_callee_scope",
        "named_target_callee_scope": {
            "direct_roots": ["inputs", "state", "args", "step", "probe"],
            "caller_step_scope": "not_directly_visible_inside_callee_body",
            "caller_data_transfer": "explicit_run_with_bindings_only",
            "step_scope": "callee_local_only",
            "let_scope": "callee_local_only",
        },
        "fan_out_surface": {
            "item_binding": "item",
            "outer_if_scope": "whole_invocation_step",
            "inner_if_scope": "per_iteration_inner_step",
            "inner_step_scope": ["inputs", "state", "step", "item", "probe"],
            "inner_register_scope": "iteration_local",
            "outer_register_scope": "aggregate_results",
            "forbidden_nested_surfaces": ["for_each", "guards"],
            "caller_step_scope": "not_directly_visible_inside_named_run_target_body",
        },
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
            "fields": ["uses", "run", "steps", "profile_switch", "value", "result", "publish", "state_set", "state_delete"],
            "message": "A workflow step must define exactly one of uses, run, steps, profile_switch, value, result, publish, state_set, or state_delete",
            "exception": "a standalone gate-only checkpoint step may omit a body form",
        },
        {
            "name": "with_requires_uses",
            "kind": "dependency",
            "field": "with",
            "requires": ["uses", "run"],
            "message": "The with field is allowed only together with uses or run",
        },
        {
            "name": "for_each_requires_invocation_body",
            "kind": "dependency",
            "field": "for_each",
            "requires": ["run", "steps"],
            "message": "The for_each field is allowed only together with run or inline steps",
        },
        {
            "name": "inline_steps_require_for_each",
            "kind": "dependency",
            "field": "steps",
            "requires": ["for_each"],
            "message": "Inline repeated step bodies require for_each",
        },
        {
            "name": "gate_forbids_register",
            "kind": "conflict",
            "fields": ["gate", "register"],
            "message": "A workflow step must not define both gate and register",
        },
    ],
    "step_forms": [
        {
            "name": "operation_call",
            "required_fields": ["name", "uses"],
            "optional_fields": ["if", "gate", "with", "register", "launcher"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "with_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
            "deprecated_optional_fields": ["launcher"],
            "preferred_alternatives": {"launcher": "routine_or_profile_context"},
        },
        {
            "name": "run_invocation",
            "required_fields": ["name", "run"],
            "optional_fields": ["if", "gate", "with", "for_each", "register"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "with_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
            "for_each_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "inline_fan_out_invocation",
            "required_fields": ["name", "for_each", "steps"],
            "optional_fields": ["if", "gate", "register"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "for_each_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "profile_switch",
            "required_fields": ["name", "profile_switch"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
        },
        {
            "name": "value",
            "required_fields": ["name", "value"],
            "optional_fields": ["if", "gate", "register"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "value_expression_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "result",
            "required_fields": ["name", "result"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "value_expression_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "publish",
            "required_fields": ["name", "publish"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "value_expression_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "state_set",
            "required_fields": ["name", "state_set"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
        },
        {
            "name": "state_delete",
            "required_fields": ["name", "state_delete"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
        },
        {
            "name": "gate_checkpoint",
            "required_fields": ["name", "gate"],
            "optional_fields": ["if"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
        },
    ],
    "surface_constraints": {
        "authored_surfaces": {
            "literal_only_fields": ["version", "workflow", "name", "uses", "run", "register", "launcher", "state_delete"],
            "literal_only_keyed_fields": ["state_set"],
            "native_condition_fields": ["let", "guards", "if", "gate"],
            "condition_field_forms": {
                "expression_string": "native_local_expression",
                "expression_embedded_string": "deprecated_compatibility",
                "structured_list": "implicit_all",
                "structured_object_operators": ["all", "any", "not"],
                "gate_structured_optional_fields": ["on_fail"],
            },
            "expression_first_value_fields": ["with", "value", "publish", "result", "for_each"],
            "expression_first_value_rules": {
                "plain_scalar_string": "local_expression",
                "quoted_string": "literal_string",
                "yaml_number_boolean_null": "native_literal",
                "nested_objects_and_lists": "recursive_leaf_rule",
                "embedded_escape_form": "${...}",
            },
        },
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
