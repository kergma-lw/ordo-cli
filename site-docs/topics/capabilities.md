# Capabilities

This page shows what Ordo supports, restricts, or deprecates.

Use this page when you need to know whether a surface is supported, restricted, or deprecated.

## Capabilities

### workflow.local_expressions

- Scope: `workflow`
- Status: `supported`

### workflow.local_expression.adapters

- Scope: `workflow`
- Status: `supported`
- Related capabilities: `workflow.local_expressions`
- Related model nodes: `workflow.local_expression.adapter_seam`, `workflow.local_expression.adapter_binding`, `workflow.local_expression.adapter.markdown`, `workflow.local_expression.adapter.text`

### workflow.include_fragments

- Scope: `workflow`
- Status: `supported`
- Related capabilities: `workflow.local_expressions`, `workflow.step.register`
- Related model nodes: `workflow.include_contract`, `workflow.include`, `workflow.include.with`, `workflow.fragment.description`, `workflow.fragment.args`, `workflow.local_expression_root.args`

### workflow.state_needs

- Scope: `workflow`
- Status: `supported`

### workflow.state_bindings

- Scope: `workflow`
- Status: `supported`

### workflow.step.state_set

- Scope: `workflow.step`
- Status: `supported`

### workflow.step.state_delete

- Scope: `workflow.step`
- Status: `supported`

### workflow.step.value

- Scope: `workflow.step`
- Status: `supported`

### runtime.launchers

- Scope: `runtime`
- Status: `deprecated`
- Related capabilities: `workflow.step.launcher`
- Related model nodes: `profile.launchers`, `workflow.step.launcher`, `workflow.step_forms.operation_call`
- Related negative rules: `workflow_step.launcher_requires_uses`
- Do not infer:
  - launcher support means launcher-centric workflow authoring is still preferred
  - a launcher is safer than a published routine by default

### workflow.step.launcher

- Scope: `workflow.step`
- Status: `deprecated`
- Related capabilities: `runtime.launchers`
- Related model nodes: `workflow.step.launcher`, `profile.launchers`, `workflow.step_forms.operation_call`
- Related negative rules: `workflow_step.launcher_requires_uses`
- Do not infer:
  - step-level launcher selection is a preferred new authoring path
  - launchers should be chosen over routine publication for new project-local automation

### workflow.step.condition

- Scope: `workflow.step`
- Status: `supported`
- Related capabilities: `workflow.step.register`, `workflow.step.value`
- Related model nodes: `workflow.step.if`, `workflow.step.register`, `workflow.step_forms.operation_call`, `workflow.step_forms.value`
- Related negative rules: `workflow_step.if_conflicts_with_register`

### workflow.step.register

- Scope: `workflow.step`
- Status: `supported`
- Related capabilities: `workflow.step.condition`, `workflow.step.outputs`, `workflow.step.value`
- Related model nodes: `workflow.step.register`, `workflow.step.uses`, `workflow.step.value`, `workflow.step_forms.operation_call`, `workflow.step_forms.value`
- Related negative rules: `workflow_step.register_requires_uses`, `workflow_step.if_conflicts_with_register`

### workflow.step.outputs

- Scope: `workflow.step`
- Status: `supported`

### workflow.branching

- Scope: `workflow`
- Status: `supported`
- Related capabilities: `workflow.step.condition`, `workflow.step.register`, `workflow.step.value`
- Related model nodes: `workflow.step.if`, `workflow.step.register`, `workflow.step_forms.operation_call`, `workflow.step_forms.value`
- Related negative rules: `workflow_step.if_conflicts_with_register`

## Negative rules

### guard_expression.no_step_root

- Surface: `guard_expression`
- Rule: Registered step references are not allowed in guard expressions
- Reason: guards run before effectful step execution and therefore cannot depend on registered step results
- Related codes: `validation.workflow.local_expression.guard.step_ref`

### guard_expression.no_adapter_write_path

- Surface: `guard_expression`
- Rule: Representation-adapter write paths such as '->...' are not allowed in guard expressions
- Reason: guard expressions may use read-only local-expression constructs but must remain pure and pre-execution-safe

### guard_expression.boolean_result_required

- Surface: `guard_expression`
- Rule: Guard expressions must evaluate to a boolean result
- Reason: guard success and failure are defined by boolean policy outcomes rather than arbitrary value production

### workflow_step.exactly_one_form

- Surface: `workflow_step`
- Rule: A workflow step must define exactly one of uses, value, state_set, or state_delete
- Reason: step forms are mutually exclusive in the workflow contract
- Related codes: `validation.workflow.step.form`

### workflow_step.with_requires_uses

- Surface: `workflow_step`
- Rule: The with field is allowed only together with uses
- Reason: runtime value inputs belong to operation-call step form only
- Related codes: `validation.workflow.step.with_without_uses`

### workflow_step.launcher_requires_uses

- Surface: `workflow_step`
- Rule: The launcher field is allowed only together with uses
- Reason: launcher selection wraps operation-call execution surfaces rather than builtin value or state steps
- Related codes: `validation.workflow.step.launcher_without_uses`

### workflow_step.register_requires_uses

- Surface: `workflow_step`
- Rule: The register field is allowed only together with uses, run, or value
- Reason: the MVP publishes registered step results only for operation-call steps, reusable run invocations, and pure value steps
- Related codes: `validation.workflow.step.register_without_uses`

### workflow_step.if_conflicts_with_register

- Surface: `workflow_step`
- Rule: The if and register fields cannot be used together in the MVP
- Reason: the MVP avoids publishing synthetic registered step results for skipped conditional steps
- Related codes: `validation.workflow.step.if_with_register`

### embedded_value_expression.step_refs_must_be_backward

- Surface: `embedded_value_expression`
- Rule: Registered step references may target only earlier steps in the same workflow
- Reason: step-result reads are order-sensitive execution-local data flow rather than random access workflow state
- Related codes: `validation.workflow.step_ref.forward`

### state_set.single_target_entry

- Surface: `state_set`
- Rule: state_set must contain exactly one target entry
- Reason: each state-set step writes one resolved state target at a time
- Related codes: `validation.workflow.state_set.entry_count`

### workflow_fragment.no_state_surface

- Surface: `workflow.include_fragments`
- Rule: Included fragments must not read, declare, or mutate runtime state
- Reason: runtime state remains a top-level workflow handoff surface rather than reusable fragment-local memory
- Related codes: `load.workflow.include.state_forbidden`

### workflow_state_role.write_after_last_read

- Surface: `workflow.state_needs`
- Rule: Logical state role writes and deletes are allowed only after the final read of that same role
- Reason: persistent runtime state should capture final cross-run handoff rather than per-run scratch flow
- Related codes: `validation.workflow.state_role.write_before_last_read`

### format_value.args_must_be_list

- Surface: `embedded_value_expression.format_object`
- Rule: format-object args must be a list when provided
- Reason: format object arguments are evaluated positionally
- Related codes: `validation.workflow.value_expr.format.args_type`

## Expression surfaces

```json
[
  {
    "boolean_operators": [
      "and",
      "or",
      "not",
      "parentheses"
    ],
    "builtins": [
      "format",
      "is_missing",
      "is_present"
    ],
    "filters": [
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
    "name": "guard_expression",
    "roots": [
      "inputs",
      "probe",
      "state"
    ]
  },
  {
    "boolean_operators": [
      "and",
      "or",
      "not",
      "parentheses"
    ],
    "builtins": [
      "format",
      "is_missing",
      "is_present"
    ],
    "filters": [
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
    "name": "step_condition",
    "roots": [
      "inputs",
      "args",
      "state",
      "step",
      "probe"
    ]
  },
  {
    "boolean_operators": [
      "and",
      "or",
      "not",
      "parentheses"
    ],
    "builtins": [
      "format",
      "is_missing",
      "is_present"
    ],
    "filters": [
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
    "name": "embedded_value_expression",
    "roots": [
      "inputs",
      "args",
      "state",
      "step",
      "probe"
    ]
  },
  {
    "boolean_operators": [],
    "builtins": [],
    "filters": [],
    "name": "state_key_reference",
    "roots": [
      "inputs"
    ]
  }
]
```

## Full JSON reference

```json
{
  "capabilities": [
    {
      "must_not_infer": [],
      "name": "workflow.local_expressions",
      "related_capabilities": [],
      "related_model_nodes": [],
      "related_negative_rules": [],
      "scope": "workflow",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.local_expression.adapters",
      "related_capabilities": [
        "workflow.local_expressions"
      ],
      "related_model_nodes": [
        "workflow.local_expression.adapter_seam",
        "workflow.local_expression.adapter_binding",
        "workflow.local_expression.adapter.markdown",
        "workflow.local_expression.adapter.text"
      ],
      "related_negative_rules": [],
      "scope": "workflow",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.include_fragments",
      "related_capabilities": [
        "workflow.local_expressions",
        "workflow.step.register"
      ],
      "related_model_nodes": [
        "workflow.include_contract",
        "workflow.include",
        "workflow.include.with",
        "workflow.fragment.description",
        "workflow.fragment.args",
        "workflow.local_expression_root.args"
      ],
      "related_negative_rules": [],
      "scope": "workflow",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.state_needs",
      "related_capabilities": [],
      "related_model_nodes": [],
      "related_negative_rules": [],
      "scope": "workflow",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.state_bindings",
      "related_capabilities": [],
      "related_model_nodes": [],
      "related_negative_rules": [],
      "scope": "workflow",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.step.state_set",
      "related_capabilities": [],
      "related_model_nodes": [],
      "related_negative_rules": [],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.step.state_delete",
      "related_capabilities": [],
      "related_model_nodes": [],
      "related_negative_rules": [],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.step.value",
      "related_capabilities": [],
      "related_model_nodes": [],
      "related_negative_rules": [],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [
        "launcher support means launcher-centric workflow authoring is still preferred",
        "a launcher is safer than a published routine by default"
      ],
      "name": "runtime.launchers",
      "related_capabilities": [
        "workflow.step.launcher"
      ],
      "related_model_nodes": [
        "profile.launchers",
        "workflow.step.launcher",
        "workflow.step_forms.operation_call"
      ],
      "related_negative_rules": [
        "workflow_step.launcher_requires_uses"
      ],
      "scope": "runtime",
      "status": "deprecated"
    },
    {
      "must_not_infer": [
        "step-level launcher selection is a preferred new authoring path",
        "launchers should be chosen over routine publication for new project-local automation"
      ],
      "name": "workflow.step.launcher",
      "related_capabilities": [
        "runtime.launchers"
      ],
      "related_model_nodes": [
        "workflow.step.launcher",
        "profile.launchers",
        "workflow.step_forms.operation_call"
      ],
      "related_negative_rules": [
        "workflow_step.launcher_requires_uses"
      ],
      "scope": "workflow.step",
      "status": "deprecated"
    },
    {
      "must_not_infer": [],
      "name": "workflow.step.condition",
      "related_capabilities": [
        "workflow.step.register",
        "workflow.step.value"
      ],
      "related_model_nodes": [
        "workflow.step.if",
        "workflow.step.register",
        "workflow.step_forms.operation_call",
        "workflow.step_forms.value"
      ],
      "related_negative_rules": [
        "workflow_step.if_conflicts_with_register"
      ],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.step.register",
      "related_capabilities": [
        "workflow.step.condition",
        "workflow.step.outputs",
        "workflow.step.value"
      ],
      "related_model_nodes": [
        "workflow.step.register",
        "workflow.step.uses",
        "workflow.step.value",
        "workflow.step_forms.operation_call",
        "workflow.step_forms.value"
      ],
      "related_negative_rules": [
        "workflow_step.register_requires_uses",
        "workflow_step.if_conflicts_with_register"
      ],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.step.outputs",
      "related_capabilities": [],
      "related_model_nodes": [],
      "related_negative_rules": [],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.branching",
      "related_capabilities": [
        "workflow.step.condition",
        "workflow.step.register",
        "workflow.step.value"
      ],
      "related_model_nodes": [
        "workflow.step.if",
        "workflow.step.register",
        "workflow.step_forms.operation_call",
        "workflow.step_forms.value"
      ],
      "related_negative_rules": [
        "workflow_step.if_conflicts_with_register"
      ],
      "scope": "workflow",
      "status": "supported"
    }
  ],
  "expression_roots": [
    {
      "name": "inputs",
      "surfaces": [
        "guard_expression",
        "state_key_reference",
        "step_condition",
        "embedded_value_expression"
      ]
    },
    {
      "name": "probe",
      "surfaces": [
        "guard_expression",
        "step_condition",
        "embedded_value_expression"
      ]
    },
    {
      "name": "args",
      "surfaces": [
        "step_condition",
        "embedded_value_expression"
      ]
    },
    {
      "name": "state",
      "surfaces": [
        "guard_expression",
        "step_condition",
        "embedded_value_expression"
      ]
    },
    {
      "name": "step",
      "surfaces": [
        "step_condition",
        "embedded_value_expression"
      ]
    }
  ],
  "expression_surfaces": [
    {
      "boolean_operators": [
        "and",
        "or",
        "not",
        "parentheses"
      ],
      "builtins": [
        "format",
        "is_missing",
        "is_present"
      ],
      "filters": [
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
      "name": "guard_expression",
      "roots": [
        "inputs",
        "probe",
        "state"
      ]
    },
    {
      "boolean_operators": [
        "and",
        "or",
        "not",
        "parentheses"
      ],
      "builtins": [
        "format",
        "is_missing",
        "is_present"
      ],
      "filters": [
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
      "name": "step_condition",
      "roots": [
        "inputs",
        "args",
        "state",
        "step",
        "probe"
      ]
    },
    {
      "boolean_operators": [
        "and",
        "or",
        "not",
        "parentheses"
      ],
      "builtins": [
        "format",
        "is_missing",
        "is_present"
      ],
      "filters": [
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
      "name": "embedded_value_expression",
      "roots": [
        "inputs",
        "args",
        "state",
        "step",
        "probe"
      ]
    },
    {
      "boolean_operators": [],
      "builtins": [],
      "filters": [],
      "name": "state_key_reference",
      "roots": [
        "inputs"
      ]
    }
  ],
  "local_expression_builtins": [
    {
      "name": "format"
    },
    {
      "name": "is_missing"
    },
    {
      "name": "is_present"
    }
  ],
  "local_expression_filters": [
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
  ],
  "negative_rules": [
    {
      "name": "guard_expression.no_step_root",
      "reason": "guards run before effectful step execution and therefore cannot depend on registered step results",
      "related_capabilities": [],
      "related_codes": [
        "validation.workflow.local_expression.guard.step_ref"
      ],
      "related_model_nodes": [],
      "rule": "Registered step references are not allowed in guard expressions",
      "surface": "guard_expression"
    },
    {
      "name": "guard_expression.no_adapter_write_path",
      "reason": "guard expressions may use read-only local-expression constructs but must remain pure and pre-execution-safe",
      "related_capabilities": [],
      "related_codes": [],
      "related_model_nodes": [],
      "rule": "Representation-adapter write paths such as '->...' are not allowed in guard expressions",
      "surface": "guard_expression"
    },
    {
      "name": "guard_expression.boolean_result_required",
      "reason": "guard success and failure are defined by boolean policy outcomes rather than arbitrary value production",
      "related_capabilities": [],
      "related_codes": [],
      "related_model_nodes": [],
      "rule": "Guard expressions must evaluate to a boolean result",
      "surface": "guard_expression"
    },
    {
      "name": "workflow_step.exactly_one_form",
      "reason": "step forms are mutually exclusive in the workflow contract",
      "related_capabilities": [],
      "related_codes": [
        "validation.workflow.step.form"
      ],
      "related_model_nodes": [],
      "rule": "A workflow step must define exactly one of uses, value, state_set, or state_delete",
      "surface": "workflow_step"
    },
    {
      "name": "workflow_step.with_requires_uses",
      "reason": "runtime value inputs belong to operation-call step form only",
      "related_capabilities": [],
      "related_codes": [
        "validation.workflow.step.with_without_uses"
      ],
      "related_model_nodes": [
        "workflow.step.with",
        "workflow.step.uses",
        "workflow.step_forms.operation_call"
      ],
      "rule": "The with field is allowed only together with uses",
      "surface": "workflow_step"
    },
    {
      "name": "workflow_step.launcher_requires_uses",
      "reason": "launcher selection wraps operation-call execution surfaces rather than builtin value or state steps",
      "related_capabilities": [
        "runtime.launchers",
        "workflow.step.launcher"
      ],
      "related_codes": [
        "validation.workflow.step.launcher_without_uses"
      ],
      "related_model_nodes": [
        "workflow.step.launcher",
        "workflow.step.uses",
        "workflow.step_forms.operation_call"
      ],
      "rule": "The launcher field is allowed only together with uses",
      "surface": "workflow_step"
    },
    {
      "name": "workflow_step.register_requires_uses",
      "reason": "the MVP publishes registered step results only for operation-call steps, reusable run invocations, and pure value steps",
      "related_capabilities": [
        "workflow.step.register",
        "workflow.step.value",
        "workflow.step.run"
      ],
      "related_codes": [
        "validation.workflow.step.register_without_uses"
      ],
      "related_model_nodes": [
        "workflow.step.register",
        "workflow.step.uses",
        "workflow.step.run",
        "workflow.step.value",
        "workflow.step_forms.operation_call",
        "workflow.step_forms.run_invocation",
        "workflow.step_forms.value"
      ],
      "rule": "The register field is allowed only together with uses, run, or value",
      "surface": "workflow_step"
    },
    {
      "name": "workflow_step.if_conflicts_with_register",
      "reason": "the MVP avoids publishing synthetic registered step results for skipped conditional steps",
      "related_capabilities": [
        "workflow.step.condition",
        "workflow.step.register",
        "workflow.step.value",
        "workflow.branching"
      ],
      "related_codes": [
        "validation.workflow.step.if_with_register"
      ],
      "related_model_nodes": [
        "workflow.step.if",
        "workflow.step.register",
        "workflow.step_forms.operation_call",
        "workflow.step_forms.value"
      ],
      "rule": "The if and register fields cannot be used together in the MVP",
      "surface": "workflow_step"
    },
    {
      "name": "embedded_value_expression.step_refs_must_be_backward",
      "reason": "step-result reads are order-sensitive execution-local data flow rather than random access workflow state",
      "related_capabilities": [],
      "related_codes": [
        "validation.workflow.step_ref.forward"
      ],
      "related_model_nodes": [],
      "rule": "Registered step references may target only earlier steps in the same workflow",
      "surface": "embedded_value_expression"
    },
    {
      "name": "state_set.single_target_entry",
      "reason": "each state-set step writes one resolved state target at a time",
      "related_capabilities": [],
      "related_codes": [
        "validation.workflow.state_set.entry_count"
      ],
      "related_model_nodes": [],
      "rule": "state_set must contain exactly one target entry",
      "surface": "state_set"
    },
    {
      "name": "workflow_fragment.no_state_surface",
      "reason": "runtime state remains a top-level workflow handoff surface rather than reusable fragment-local memory",
      "related_capabilities": [],
      "related_codes": [
        "load.workflow.include.state_forbidden"
      ],
      "related_model_nodes": [],
      "rule": "Included fragments must not read, declare, or mutate runtime state",
      "surface": "workflow.include_fragments"
    },
    {
      "name": "workflow_state_role.write_after_last_read",
      "reason": "persistent runtime state should capture final cross-run handoff rather than per-run scratch flow",
      "related_capabilities": [],
      "related_codes": [
        "validation.workflow.state_role.write_before_last_read"
      ],
      "related_model_nodes": [],
      "rule": "Logical state role writes and deletes are allowed only after the final read of that same role",
      "surface": "workflow.state_needs"
    },
    {
      "name": "format_value.args_must_be_list",
      "reason": "format object arguments are evaluated positionally",
      "related_capabilities": [],
      "related_codes": [
        "validation.workflow.value_expr.format.args_type"
      ],
      "related_model_nodes": [],
      "rule": "format-object args must be a list when provided",
      "surface": "embedded_value_expression.format_object"
    }
  ]
}
```
