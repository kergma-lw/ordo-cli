# Authoring model

This page outlines the main authoring contracts used in workflows, playbooks, profiles, and runtime state.

Use this page when you need field-level contract details for authoring work.

## Full JSON reference

```json
{
  "document_kind": "model",
  "local_expressions": {
    "pipeline_filters": [
      {
        "argument_count": 0,
        "input_type": "string",
        "name": "lower",
        "output_type": "string"
      },
      {
        "argument_count": 0,
        "input_type": "string",
        "name": "trim",
        "output_type": "string"
      },
      {
        "argument_count": 0,
        "input_type": "string",
        "name": "slug",
        "output_type": "string"
      },
      {
        "argument_count": 1,
        "input_type": "json",
        "name": "eq",
        "output_type": "boolean"
      },
      {
        "argument_count": 1,
        "input_type": "json",
        "name": "ne",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "boolean",
        "name": "not",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "is_string",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "is_number",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "is_integer",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "is_boolean",
        "output_type": "boolean"
      },
      {
        "argument_count": 1,
        "input_type": "json",
        "name": "in",
        "output_type": "boolean"
      },
      {
        "argument_count": 1,
        "input_type": "json",
        "name": "field",
        "output_type": "json"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "flatten",
        "output_type": "json"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "first",
        "output_type": "json"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "last",
        "output_type": "json"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "length",
        "output_type": "number"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "unique",
        "output_type": "json"
      }
    ]
  },
  "playbook": {
    "activation_semantics": {
      "discovery": {
        "missing": "playbook.discovery.missing",
        "path": ".ordo/ordo.yaml",
        "strategy": "cwd_relative_single_path"
      },
      "pre_run": {
        "effect": "executes_before_requested_workflow_in_same_runtime_session",
        "item_type": "pre_run_entry",
        "launch_context_boundary": "playbook_owned",
        "optional": [
          "state_bindings"
        ],
        "requires": [
          "file"
        ],
        "state_dependency_boundary": "must_not_widen_main_workflow_state_contract"
      },
      "profile_entries": {
        "requires": [
          "file"
        ]
      },
      "state_entries": {
        "requires": [
          "path"
        ]
      },
      "workflow_entries": {
        "optional": [
          "description",
          "category",
          "when",
          "working_directory",
          "state_bindings"
        ],
        "requires": [
          "file"
        ]
      }
    },
    "defaults_fields": [
      {
        "name": "profile",
        "required": false,
        "runtime_effect": "selects_active_profile",
        "type": "string"
      },
      {
        "expression_allowed_roots": [
          "inputs"
        ],
        "expression_forbidden_roots": [
          "state",
          "step"
        ],
        "expression_surface": "activation_input_value_expression",
        "expression_syntax": "${...}",
        "name": "working_directory",
        "required": false,
        "resolution_base": "playbook_dir",
        "runtime_effect": "sets_default_execution_working_directory",
        "type": "string"
      }
    ],
    "discovery": {
      "path": ".ordo/ordo.yaml"
    },
    "document_kind": "playbook",
    "pre_run_entry_fields": [
      {
        "name": "file",
        "required": true,
        "type": "string"
      },
      {
        "documentation_role": "playbook_owned_pre_run_state_bindings",
        "name": "state_bindings",
        "required": false,
        "type": "object"
      }
    ],
    "profile_entry_fields": [
      {
        "name": "file",
        "required": true,
        "type": "string"
      }
    ],
    "state_entry_fields": [
      {
        "name": "path",
        "required": true,
        "type": "string"
      }
    ],
    "top_level_fields": [
      {
        "name": "version",
        "required": true,
        "type": "integer"
      },
      {
        "name": "pre_run",
        "required": false,
        "type": "array"
      },
      {
        "name": "states",
        "required": true,
        "type": "object"
      },
      {
        "name": "defaults",
        "required": false,
        "type": "object"
      },
      {
        "name": "workflows",
        "required": true,
        "type": "object"
      },
      {
        "name": "profiles",
        "required": false,
        "type": "object"
      }
    ],
    "version": 1,
    "workflow_entry_fields": [
      {
        "name": "file",
        "required": true,
        "type": "string"
      },
      {
        "documentation_role": "project_local_workflow_summary",
        "name": "description",
        "required": false,
        "type": "string"
      },
      {
        "documentation_role": "project_local_workflow_catalog_group",
        "name": "category",
        "required": false,
        "runtime_effect": "published_metadata_only",
        "type": "string"
      },
      {
        "documentation_role": "operator_workflow_selection_guidance",
        "name": "when",
        "required": false,
        "runtime_effect": "published_metadata_only",
        "type": "string"
      },
      {
        "expression_allowed_roots": [
          "inputs"
        ],
        "expression_forbidden_roots": [
          "state",
          "step"
        ],
        "expression_surface": "activation_input_value_expression",
        "expression_syntax": "${...}",
        "name": "working_directory",
        "required": false,
        "resolution_base": "playbook_dir",
        "runtime_effect": "sets_execution_working_directory",
        "type": "string"
      },
      {
        "name": "state_bindings",
        "required": false,
        "type": "object"
      }
    ]
  },
  "profile": {
    "compose_semantics": {
      "checks": {
        "order": "left_to_right",
        "strategy": "deduplicated_union"
      },
      "inputs": {
        "conflict": "validation_error",
        "strategy": "first_writer_wins"
      },
      "launchers": {
        "conflict": "validation_error",
        "conflict_key": "launcher_name",
        "status": "deprecated",
        "strategy": "first_writer_wins"
      },
      "overrides": {
        "conflict": "validation_error",
        "conflict_key": "target"
      },
      "working_directory": {
        "conflict": "validation_error",
        "strategy": "first_writer_wins"
      }
    },
    "document_kind": "profile",
    "launcher_fields": [
      {
        "name": "file",
        "required": false,
        "type": "string"
      },
      {
        "name": "connector",
        "required": false,
        "type": "string"
      },
      {
        "name": "before",
        "required": false,
        "type": "string"
      },
      {
        "name": "after",
        "required": false,
        "type": "string"
      }
    ],
    "override_fields": [
      {
        "name": "target",
        "required": true,
        "type": "string"
      },
      {
        "name": "with",
        "required": false,
        "type": "object"
      },
      {
        "name": "reason",
        "required": false,
        "type": "string"
      }
    ],
    "top_level_fields": [
      {
        "name": "name",
        "required": true,
        "type": "string"
      },
      {
        "name": "inputs",
        "required": false,
        "runtime_effect": "applies_missing_workflow_inputs",
        "type": "object"
      },
      {
        "expression_allowed_roots": [
          "inputs"
        ],
        "expression_forbidden_roots": [
          "state",
          "step"
        ],
        "expression_surface": "activation_input_value_expression",
        "expression_syntax": "${...}",
        "name": "working_directory",
        "required": false,
        "resolution_base": "playbook_dir",
        "runtime_effect": "sets_profile_execution_working_directory",
        "type": "string"
      },
      {
        "name": "checks",
        "required": false,
        "runtime_effect": "published_metadata_only",
        "type": "array"
      },
      {
        "name": "overrides",
        "required": false,
        "runtime_effect": "published_metadata_only",
        "type": "array"
      },
      {
        "name": "launchers",
        "preferred_alternative": "published_routines",
        "required": false,
        "runtime_effect": "publishes_profile_scoped_launchers",
        "status": "deprecated",
        "type": "object"
      }
    ],
    "workflow_apply_semantics": {
      "checks": {
        "mutates_workflow_contract": false
      },
      "inputs": {
        "conflict": "validation_error",
        "may_add_missing": true,
        "may_override_explicit_workflow_values": false
      },
      "launchers": {
        "mutates_workflow_steps": false,
        "published_as_explicit_metadata": true,
        "status": "deprecated"
      },
      "overrides": {
        "mutates_workflow_steps": false,
        "published_as_explicit_metadata": true
      },
      "working_directory": {
        "mutates_workflow_steps": false,
        "published_as_explicit_metadata": true
      }
    }
  },
  "representation_adapters": {
    "families": [
      {
        "actions": [
          "add",
          "append",
          "replace",
          "remove"
        ],
        "name": "markdown",
        "selectors": [
          "prelude",
          "[\"title\"]",
          "[n]",
          ".blocks(\"kind\")"
        ],
        "shortcuts": [
          "list",
          "lists",
          "list_items",
          "task_list",
          "task_lists",
          "task_list_items",
          "paragraph",
          "paragraphs",
          "prelude"
        ],
        "summary": "Select and transform markdown sections, blocks, and lists through a family-owned path surface."
      },
      {
        "actions": [
          "append",
          "replace",
          "remove"
        ],
        "name": "text",
        "selectors": [
          "lines",
          "find(\"literal\")",
          "finds(\"literal\")",
          "before(\"literal\")",
          "after(\"literal\")",
          "[n]"
        ],
        "shortcuts": [],
        "summary": "Select and transform plain-text roots through literal narrowing, line projection, and terminal text mutation."
      }
    ],
    "shared_seam": {
      "family_owned_body": true,
      "host_binding_rules": [
        "host references do not appear bare inside adapter-owned body syntax",
        "outer bindings are resolved before adapter-family evaluation"
      ],
      "outer_binding_form": " with{...}",
      "read_write_boundary": {
        "read": "returns selected_or_derived_value",
        "write": "returns updated_root_value"
      }
    }
  },
  "state": {
    "document_kind": "state_contract",
    "invalid_path_rules": [
      {
        "message": "state path must start with 'state'",
        "name": "root_must_be_state"
      },
      {
        "message": "state path key reference must use dotted inputs form such as 'inputs.task_key'",
        "name": "key_reference_must_use_dotted_inputs"
      },
      {
        "message": "state path must not contain trailing content",
        "name": "no_trailing_content"
      }
    ],
    "path_forms": {
      "root": "state",
      "root_reference": "inputs",
      "shape": "state.<role>[inputs.<key>][.<field>...]",
      "supports_hyphenated_roles": true,
      "supports_nested_fields": true
    },
    "runtime_rules": [
      {
        "error_code": "runtime.state.binding_missing",
        "message": "state role must be bound before runtime access",
        "name": "bound_role_required"
      },
      {
        "error_code": "runtime.state.key_invalid",
        "message": "state key reference must resolve to a scalar value",
        "name": "scalar_key_required"
      },
      {
        "error_code": "runtime.state.declaration_missing",
        "message": "undeclared state locations are runtime errors",
        "name": "declared_location_required"
      }
    ],
    "storage_document": {
      "root_type": "object",
      "top_level_keys": "user-defined"
    },
    "workflow_surface": {
      "state_binding_field": "state_bindings",
      "state_needs_field": "state_needs",
      "step_state_delete_field": "state_delete",
      "step_state_set_field": "state_set",
      "storage_targets_field": "states"
    }
  },
  "workflow": {
    "block_forms": [
      {
        "name": "guard_block",
        "optional_fields": [],
        "required_fields": [
          "guards"
        ]
      },
      {
        "name": "step_block",
        "optional_fields": [],
        "required_fields": [
          "steps"
        ]
      },
      {
        "name": "include_block",
        "optional_fields": [
          "with"
        ],
        "required_fields": [
          "include"
        ]
      }
    ],
    "document_kind": "workflow",
    "guard_forms": [
      {
        "name": "operation_call",
        "shape": {
          "uses": "string",
          "with": "object"
        },
        "status": "compatibility_only"
      },
      {
        "name": "expression",
        "shape": "string",
        "status": "stable_preferred"
      }
    ],
    "include_contract": {
      "authoring_role": "workflow_fragment_reuse",
      "call_fields": [
        {
          "name": "include",
          "required": true,
          "type": "string"
        },
        {
          "authoring_role": "fragment_argument_bindings",
          "name": "with",
          "required": false,
          "type": "object"
        }
      ],
      "cycle_detection": "current_expansion_stack",
      "directive_field": "include",
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
        "load.workflow.include.args.type"
      ],
      "expansion_semantics": "resolve_bind_expand_whole_node_replacement",
      "extension_probe_order": [
        ".yaml",
        ".yml"
      ],
      "fragment_argument_access_surface": "args.name",
      "fragment_argument_declaration_forms": [
        {
          "name": "required_short_form",
          "shape": "arg_name: string_type_name"
        },
        {
          "name": "object_form",
          "shape": {
            "default": "json_value_optional",
            "required": "boolean_optional",
            "type": "string"
          }
        }
      ],
      "fragment_argument_default_semantics": {
        "default_makes_argument_optional": true,
        "default_null_is_valid": true,
        "omitted_argument_is_distinct_from_explicit_null_binding": true
      },
      "fragment_metadata_fields": [
        {
          "name": "description",
          "required": false,
          "type": "string"
        },
        {
          "authoring_role": "declares_fragment_local_inputs",
          "name": "args",
          "required": false,
          "type": "object"
        }
      ],
      "max_depth": 32,
      "search_order": [
        "including_file_dir",
        "launch_dir",
        "launch_dir_dot_ordo",
        "home_dot_ordo",
        "built_in_includes_dir"
      ],
      "state_scope": "global_across_assembled_workflow",
      "step_scope": "local_to_workflow_or_fragment_expansion_scope",
      "stops_on_first_match": true,
      "targets": "files_only",
      "validation_boundary": "assembled_workflow_after_include_expansion_and_argument_binding"
    },
    "inputs_contract": {
      "access_surface": "inputs.name",
      "declaration_fields": [
        {
          "authoring_role": "input_meaning",
          "name": "description",
          "required": false,
          "type": "string"
        },
        {
          "authoring_role": "input_guidance",
          "name": "hint",
          "required": false,
          "type": "string",
          "validation_effect": "none"
        }
      ],
      "declaration_shape": "mapping",
      "declared_keys_required_at_activation": true,
      "empty_string_is_distinct_value": true,
      "null_is_distinct_from_missing": true,
      "rejects_unknown_activation_inputs": true,
      "scope": "global",
      "validated_by": "runtime"
    },
    "run_contract": {
      "authoring_role": "workflow_fragment_invocation",
      "call_fields": [
        {
          "name": "run",
          "required": true,
          "type": "string"
        },
        {
          "authoring_role": "caller_scoped_invocation_condition",
          "name": "if",
          "required": false,
          "type": "string"
        },
        {
          "authoring_role": "fragment_argument_bindings",
          "name": "with",
          "required": false,
          "type": "object"
        }
      ],
      "caller_scoped_binding_surface": [
        "inputs",
        "state",
        "step"
      ],
      "caller_scoped_condition_surface": [
        "inputs",
        "state",
        "step"
      ],
      "directive_field": "run",
      "execution_semantics": "runtime_scoped_fragment_invocation",
      "fragment_argument_access_surface": "args.name",
      "surface_kind": "step_form"
    },
    "step_form_rules": [
      {
        "fields": [
          "uses",
          "run",
          "profile_switch",
          "value",
          "result",
          "publish",
          "state_set",
          "state_delete"
        ],
        "kind": "exclusive_choice",
        "message": "A workflow step must define exactly one of uses, run, profile_switch, value, result, publish, state_set, or state_delete",
        "name": "exactly_one_step_form"
      },
      {
        "field": "with",
        "kind": "dependency",
        "message": "The with field is allowed only together with uses or run",
        "name": "with_requires_uses",
        "requires": [
          "uses",
          "run"
        ]
      }
    ],
    "step_forms": [
      {
        "deprecated_optional_fields": [
          "launcher"
        ],
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "operation_call",
        "optional_fields": [
          "if",
          "with",
          "register",
          "launcher"
        ],
        "preferred_alternatives": {
          "launcher": "routine_or_profile_context"
        },
        "required_fields": [
          "name",
          "uses"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "run_invocation",
        "optional_fields": [
          "if",
          "with",
          "for_each",
          "register"
        ],
        "required_fields": [
          "name",
          "run"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "profile_switch",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "profile_switch"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "value",
        "optional_fields": [
          "if",
          "register"
        ],
        "required_fields": [
          "name",
          "value"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "result",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "result"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "publish",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "publish"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "state_set",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "state_set"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "state_delete",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "state_delete"
        ]
      }
    ],
    "surface_constraints": {
      "guard_expression": {
        "allowed_builtins": [
          "format",
          "is_missing",
          "is_present"
        ],
        "allowed_filters": [
          "lower",
          "trim",
          "slug",
          "eq",
          "ne",
          "not",
          "is_string",
          "is_number",
          "is_integer",
          "is_boolean",
          "in",
          "field",
          "flatten",
          "first",
          "last",
          "length",
          "unique"
        ],
        "allowed_roots": [
          "inputs",
          "probe",
          "state"
        ],
        "boolean_operators": [
          "and",
          "or",
          "not",
          "parentheses"
        ],
        "representation_adapter_policy": {
          "forbidden_write_surface": "->...",
          "read_only_allowed": true,
          "write_paths_forbidden": true
        },
        "result_contract": {
          "non_boolean_result": "error",
          "required_output_type": "boolean"
        }
      },
      "runtime_value_surface": {
        "allowed_builtins": [
          "format",
          "is_missing",
          "is_present"
        ],
        "allowed_filters": [
          "lower",
          "trim",
          "slug",
          "eq",
          "ne",
          "not",
          "is_string",
          "is_number",
          "is_integer",
          "is_boolean",
          "in",
          "field",
          "flatten",
          "first",
          "last",
          "length",
          "unique"
        ],
        "allowed_roots": [
          "inputs",
          "args",
          "state",
          "step"
        ],
        "boolean_operators": [
          "and",
          "or",
          "not",
          "parentheses"
        ]
      }
    },
    "top_level_fields": [
      {
        "name": "version",
        "required": true,
        "type": "integer"
      },
      {
        "name": "workflow",
        "required": true,
        "type": "string"
      },
      {
        "activation_requirement": "all_declared_keys_required",
        "authoring_role": "declares_global_activation_inputs",
        "name": "inputs",
        "required": false,
        "type": "object",
        "unknown_input_policy": "reject_unknown_inputs"
      },
      {
        "authoring_role": "declares_workflow_local_named_expressions",
        "name": "let",
        "required": false,
        "type": "object"
      },
      {
        "name": "state_needs",
        "required": false,
        "type": "object"
      },
      {
        "name": "blocks",
        "required": false,
        "type": "array"
      }
    ],
    "version": 0
  }
}
```
