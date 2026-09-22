# Capabilities

This page shows what Ordo supports, restricts, or deprecates.

Use this page when you need to know whether a surface is supported, restricted, or deprecated.

## Capabilities

### workflow.local_expressions

- Scope: `workflow`
- Status: `supported`
- Related model nodes: `workflow.local_expression.filter`, `workflow.local_expression.builtin`, `workflow.local_expression.adapter`

### workflow.local_expression.adapter

- Scope: `workflow`
- Status: `supported`
- Related capabilities: `workflow.local_expressions`
- Related model nodes: `workflow.local_expression.adapter_seam`, `workflow.local_expression.adapter_binding`, `workflow.local_expression.adapter.json`, `workflow.local_expression.adapter.key_value`, `workflow.local_expression.adapter.markdown`, `workflow.local_expression.adapter.text`, `workflow.local_expression.adapter.yaml`

### workflow.state_bindings

- Scope: `workflow`
- Status: `supported`
- Related model nodes: `playbook.states`, `state.workflow_surface.state_binding_field`, `state.workflow_surface.storage_targets_field`, `workflow.step.state_set`, `workflow.step.state_delete`

### workflow.state_needs

- Scope: `workflow`
- Status: `supported`
- Related capabilities: `workflow.state_bindings`
- Related model nodes: `state.workflow_surface.state_needs_field`, `playbook.states`, `state.workflow_surface.state_binding_field`

### workflow.step.state_set

- Scope: `workflow.step`
- Status: `supported`
- Related capabilities: `workflow.state_bindings`
- Related model nodes: `state.workflow_surface.step_state_set_field`, `workflow.step_forms.state_set`
- Related negative rules: `state_set.single_target_entry`

### workflow.step.state_delete

- Scope: `workflow.step`
- Status: `supported`
- Related capabilities: `workflow.state_bindings`
- Related model nodes: `state.workflow_surface.step_state_delete_field`, `workflow.step_forms.state_delete`

### workflow.step.value

- Scope: `workflow.step`
- Status: `supported`
- Related capabilities: `workflow.local_expressions`
- Related model nodes: `workflow.step_forms.value`, `workflow.step.result`, `workflow.step.publish`

### workflow.include_fragments

- Scope: `workflow`
- Status: `supported`
- Related capabilities: `workflow.local_expressions`, `workflow.step.register`
- Related model nodes: `workflow.include_contract`, `workflow.include`, `workflow.include.with`, `workflow.fragment.description`, `workflow.fragment.args`, `workflow.local_expression_root.args`

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
- Related model nodes: `workflow.step.if`, `workflow.step.gate`, `workflow.step.register`, `workflow.step_forms.operation_call`, `workflow.step_forms.gate_checkpoint`, `workflow.step_forms.value`
- Related negative rules: `workflow_step.if_conflicts_with_register`, `workflow_step.gate_conflicts_with_register`
- Do not infer:
  - one shared boolean condition surface means if and gate do the same semantic job
  - if is the catch-all control mechanism for applicability, admission, and local branching

### workflow.step.register

- Scope: `workflow.step`
- Status: `supported`
- Related capabilities: `workflow.step.condition`, `workflow.step.outputs`, `workflow.step.value`
- Related model nodes: `workflow.step.register`, `workflow.step.uses`, `workflow.step.value`, `workflow.step_forms.operation_call`, `workflow.step_forms.value`
- Related negative rules: `workflow_step.register_requires_uses`, `workflow_step.if_conflicts_with_register`, `workflow_step.gate_conflicts_with_register`

### workflow.step.outputs

- Scope: `workflow.step`
- Status: `supported`
- Related capabilities: `workflow.step.register`, `workflow.step.value`
- Related model nodes: `workflow.step.name`, `workflow.step.register`, `workflow.step.value`, `workflow.step_forms.operation_call`, `workflow.step_forms.run_invocation`
- Do not infer:
  - step outputs are ambient global context instead of explicit reads from named or registered steps

### workflow.branching

- Scope: `workflow`
- Status: `supported`
- Related capabilities: `workflow.step.condition`, `workflow.step.register`, `workflow.step.value`
- Related model nodes: `workflow.step.if`, `workflow.step.register`, `workflow.step_forms.operation_call`, `workflow.step_forms.value`
- Related negative rules: `workflow_step.if_conflicts_with_register`
- Do not infer:
  - branching support means if should carry workflow applicability or admission decisions
  - workflow branching is best modeled by stretching if across every conditional concern

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

### workflow_step.gate_conflicts_with_register

- Surface: `workflow_step`
- Rule: The gate and register fields cannot be used together; split the gate into a standalone checkpoint step before the registered step
- Reason: gate admission should stay separate from step-result publication so blocked steps never need to imply a registered output surface
- Related codes: `validation.workflow.step.gate_register_conflict`, `load.step.gate_register_conflict`

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
- Rule: Before binding, logical state role writes and deletes are allowed only after the final read of that same role; bound validation instead compares actual storage in each access context
- Reason: persistent runtime state should capture final cross-run handoff rather than per-run scratch flow
- Related codes: `validation.workflow.state_role.write_before_last_read`

### workflow_state_storage.write_after_last_read

- Surface: `workflow.state_bindings`
- Rule: After binding, write or delete only after the final read of the same actual file, regardless of role, state name, profile, key, or field
- Reason: relative paths resolve in each access context; normalized paths, symlinks, and existing hardlinks can alias, while the same role may resolve to different files and be valid
- Related codes: `validation.workflow.state_storage.write_before_last_read`

### workflow_state_storage.relevant_identity_required

- Surface: `workflow.state_bindings`
- Rule: Conservatively reject early only relevant write/later-read pairs whose storage identity cannot be established; this is not a proven ordering violation
- Reason: validation must precede observations and effects; uncertain context alone does not reject read-only, read-before-write, or known-disjoint access; individual child validation is not a cross-invocation or cross-iteration guarantee, and no new loop mutation ban is added
- Related codes: `validation.workflow.state_storage.identity_unresolved`

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
      "lookup",
      "only",
      "flatten",
      "first",
      "last",
      "length",
      "unique",
      "catch",
      "not_found"
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
      "lookup",
      "only",
      "flatten",
      "first",
      "last",
      "length",
      "unique",
      "catch",
      "not_found"
    ],
    "name": "step_condition",
    "roots": [
      "inputs",
      "args",
      "item",
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
      "lookup",
      "only",
      "flatten",
      "first",
      "last",
      "length",
      "unique",
      "catch",
      "not_found"
    ],
    "name": "embedded_value_expression",
    "roots": [
      "inputs",
      "args",
      "item",
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
      "lookup",
      "only",
      "flatten",
      "first",
      "last",
      "length",
      "unique",
      "catch",
      "not_found"
    ],
    "name": "include_binding_expression",
    "roots": [
      "inputs",
      "item",
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
      "lookup",
      "only",
      "flatten",
      "first",
      "last",
      "length",
      "unique",
      "catch",
      "not_found"
    ],
    "name": "state_key_expression",
    "roots": [
      "inputs",
      "args",
      "item",
      "state",
      "step"
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
      "related_model_nodes": [
        "workflow.local_expression.filter",
        "workflow.local_expression.builtin",
        "workflow.local_expression.adapter"
      ],
      "related_negative_rules": [],
      "scope": "workflow",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.local_expression.adapter",
      "related_capabilities": [
        "workflow.local_expressions"
      ],
      "related_model_nodes": [
        "workflow.local_expression.adapter_seam",
        "workflow.local_expression.adapter_binding",
        "workflow.local_expression.adapter.json",
        "workflow.local_expression.adapter.key_value",
        "workflow.local_expression.adapter.markdown",
        "workflow.local_expression.adapter.text",
        "workflow.local_expression.adapter.yaml"
      ],
      "related_negative_rules": [],
      "scope": "workflow",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.state_bindings",
      "related_capabilities": [],
      "related_model_nodes": [
        "playbook.states",
        "state.workflow_surface.state_binding_field",
        "state.workflow_surface.storage_targets_field",
        "workflow.step.state_set",
        "workflow.step.state_delete"
      ],
      "related_negative_rules": [],
      "scope": "workflow",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.state_needs",
      "related_capabilities": [
        "workflow.state_bindings"
      ],
      "related_model_nodes": [
        "state.workflow_surface.state_needs_field",
        "playbook.states",
        "state.workflow_surface.state_binding_field"
      ],
      "related_negative_rules": [],
      "scope": "workflow",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.step.state_set",
      "related_capabilities": [
        "workflow.state_bindings"
      ],
      "related_model_nodes": [
        "state.workflow_surface.step_state_set_field",
        "workflow.step_forms.state_set"
      ],
      "related_negative_rules": [
        "state_set.single_target_entry"
      ],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.step.state_delete",
      "related_capabilities": [
        "workflow.state_bindings"
      ],
      "related_model_nodes": [
        "state.workflow_surface.step_state_delete_field",
        "workflow.step_forms.state_delete"
      ],
      "related_negative_rules": [],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [],
      "name": "workflow.step.value",
      "related_capabilities": [
        "workflow.local_expressions"
      ],
      "related_model_nodes": [
        "workflow.step_forms.value",
        "workflow.step.result",
        "workflow.step.publish"
      ],
      "related_negative_rules": [],
      "scope": "workflow.step",
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
      "must_not_infer": [
        "one shared boolean condition surface means if and gate do the same semantic job",
        "if is the catch-all control mechanism for applicability, admission, and local branching"
      ],
      "name": "workflow.step.condition",
      "related_capabilities": [
        "workflow.step.register",
        "workflow.step.value"
      ],
      "related_model_nodes": [
        "workflow.step.if",
        "workflow.step.gate",
        "workflow.step.register",
        "workflow.step_forms.operation_call",
        "workflow.step_forms.gate_checkpoint",
        "workflow.step_forms.value"
      ],
      "related_negative_rules": [
        "workflow_step.if_conflicts_with_register",
        "workflow_step.gate_conflicts_with_register"
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
        "workflow_step.if_conflicts_with_register",
        "workflow_step.gate_conflicts_with_register"
      ],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [
        "step outputs are ambient global context instead of explicit reads from named or registered steps"
      ],
      "name": "workflow.step.outputs",
      "related_capabilities": [
        "workflow.step.register",
        "workflow.step.value"
      ],
      "related_model_nodes": [
        "workflow.step.name",
        "workflow.step.register",
        "workflow.step.value",
        "workflow.step_forms.operation_call",
        "workflow.step_forms.run_invocation"
      ],
      "related_negative_rules": [],
      "scope": "workflow.step",
      "status": "supported"
    },
    {
      "must_not_infer": [
        "branching support means if should carry workflow applicability or admission decisions",
        "workflow branching is best modeled by stretching if across every conditional concern"
      ],
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
  "connector_authoring_guidance": "Connector-author SDK: ctx.call(name, *, inputs=None) supports nonempty already-resolved inputs only for same-family probe dependencies. Full references (gh.pr.list) and local dotted names (pr.list) work; values are not reevaluated as expressions or templates. Omitted inputs or None preserve legacy no-input behavior. Cross-family calls and probe-to-action hidden mutation are rejected; no new action composition. Inspect connector.authoring for dependency boundaries and verified examples.",
  "expression_roots": [
    {
      "name": "inputs",
      "surfaces": [
        "guard_expression",
        "state_key_expression",
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
      "name": "item",
      "surfaces": [
        "step_condition",
        "embedded_value_expression",
        "include_binding_expression"
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
        "lookup",
        "only",
        "flatten",
        "first",
        "last",
        "length",
        "unique",
        "catch",
        "not_found"
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
        "lookup",
        "only",
        "flatten",
        "first",
        "last",
        "length",
        "unique",
        "catch",
        "not_found"
      ],
      "name": "step_condition",
      "roots": [
        "inputs",
        "args",
        "item",
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
        "lookup",
        "only",
        "flatten",
        "first",
        "last",
        "length",
        "unique",
        "catch",
        "not_found"
      ],
      "name": "embedded_value_expression",
      "roots": [
        "inputs",
        "args",
        "item",
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
        "lookup",
        "only",
        "flatten",
        "first",
        "last",
        "length",
        "unique",
        "catch",
        "not_found"
      ],
      "name": "include_binding_expression",
      "roots": [
        "inputs",
        "item",
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
        "lookup",
        "only",
        "flatten",
        "first",
        "last",
        "length",
        "unique",
        "catch",
        "not_found"
      ],
      "name": "state_key_expression",
      "roots": [
        "inputs",
        "args",
        "item",
        "state",
        "step"
      ]
    }
  ],
  "gh_pr_create_guidance": "GitHub creation: gh.pr.create requires head, base, title, and an explicit boolean draft; body defaults to empty. repository is optional: valid explicit OWNER/REPO overrides connector_contexts.gh.repository; omitted or null uses context, malformed explicit input fails without fallback. head_repository is a full source OWNER/REPO, default target repository; explicit cross-repository intent requires it, with no fork guessing. head_owner is an optional consistency assertion, otherwise derived from the exact source repository. Same-organization head_repo API argument is derived repository NAME. Reject same-branch/same-repository requests. The action uses ctx.call('gh.pr.list', inputs=...) with resolved repository/head/head_owner/base and state: open; require complete traversal and exact case-insensitive head_repository_key identity. One exact open match including draft returns non-OK already_exists with pull_number, url, created=false and no POST; multiple matches return ambiguous; unknown identity and list failure return precheck_failed. No existing match permits one POST. Only validated HTTP 201 means created=true; malformed 201, timeout, or server failure returns creation_unknown with created=null. HTTP 422 is generic create_refused, not universal duplicate evidence; preserve API errors. No POST retry or automatic readback reconciliation. This is not find-or-reuse or closed-history policy: workflow-owned gh.pr.list state: all classification precedes create's separate open check. Concurrent duplicates can race the check: no atomic uniqueness or exactly-once guarantee. No CI waiting, merge, push, fork, branch cleanup, or extra issue/project operations. Inspect connector.gh.pr.create.",
  "gh_pr_merge_guidance": "GitHub async merge: gh.pr observes head/base/test-merge identity and stack_state (standalone/stacked/unknown) plus stack; gh.pr.checks observes CI evidence. gh.pr.merge requires expected_head_sha from the accepted CI head, never a freshly fetched replacement. For gh.pr.merge and gh.pr.merge.request, repository is optional: a valid explicit OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error. For checks on candidate M with verified base B and head H, submit expected_head_sha=H, not M. The first version rejects stacked PRs and unknown scope before submission; there is no atomic base or stack guarantee. Save the action result request_id UUID for gh.pr.merge.request: accepted submission is not completion. Observe pending/merged/failed/enqueued once; unavailable is not failed and enqueued is not merged. Only an exact matching existing request is reusable. No polling, queue administration, or admin bypass is provided. GitHub automatic issue closing and branch configuration effects are outside this action. Inspect connector.gh.pr.merge and connector.gh.pr.merge.request for the verified canonical workflow example.",
  "graph_context": "Graph does not read saved state, run probes, or recommend what to do next. Use workflows show <workflow> for inputs, check <workflow> to check whether it can run, explain <workflow> to understand why, and next for a recommendation in the current environment.",
  "graph_guidance": "Show how workflows connect through persistent state. Use ordo-playbook graph to explore related workflows, where they write shared data, and where that data is removed. No active task is required.",
  "graph_parameters": "parameter stands for a key that has not been selected; the relationship applies to a matching context instance. Use graph --json for detailed dependencies, conditions, and unresolved relationships. Technical reference: docs/static-graph.md and meta/model/runtime/graph-v1.md.",
  "graph_presentation": "Read +field as a write, −field as a deletion, and ? as a conditional change. A write need not be the first write; −context removes the selected context.",
  "graph_roles": "↔ marks the same workflow: state/kind identifies another role; (reference) is a leaf sighting, not another execution. A deletion appears near the related data's users; this does not require running every reader before deleting the data.",
  "graph_source_placement": "Shared context: writers → readers, not execution order. A free reader root is marked (data use; alternative sources) because it uses data without mutating the context. This shows shared data, not a mandatory sequence: guards and check determine applicability, and alternative ends are not sequential steps. Playbook order helps arrange workflows when their relationships leave a choice. Writers and deletions can also be branches. When sources already form a chain, the deepest source is the parent; also reads from keeps other sources visible. Distinct data from incomparable sources is shown under each source: the first source in display order holds the full occurrence, and ↔ (reference) leaves show the same operation without repeating its subtree. Alternative writers of the same data stay together. reads from: name? marks known conditional or fallback data use, separately from +field?. Fallback reads still count as data use. A missing graph edge does not prove independence in external systems.",
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
      "argument_count": 1,
      "input_type": "json",
      "name": "lookup",
      "output_type": "json"
    },
    {
      "argument_count": 1,
      "authored_form": "only(field=value) / only(field!=value)",
      "input_type": "json",
      "name": "only",
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
    },
    {
      "argument_count": 2,
      "authored_form": "catch([\"issue_not_found\", \"*_not_found\"], false)",
      "input_type": "json",
      "name": "catch",
      "output_type": "json"
    },
    {
      "argument_count": 0,
      "input_type": "json",
      "name": "not_found",
      "output_type": "boolean"
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
      "name": "workflow_step.gate_conflicts_with_register",
      "reason": "gate admission should stay separate from step-result publication so blocked steps never need to imply a registered output surface",
      "related_capabilities": [
        "workflow.step.condition",
        "workflow.step.register",
        "workflow.step.value"
      ],
      "related_codes": [
        "validation.workflow.step.gate_register_conflict",
        "load.step.gate_register_conflict"
      ],
      "related_model_nodes": [
        "workflow.step.gate",
        "workflow.step.register",
        "workflow.step_forms.gate_checkpoint",
        "workflow.step_forms.operation_call",
        "workflow.step_forms.value"
      ],
      "rule": "The gate and register fields cannot be used together; split the gate into a standalone checkpoint step before the registered step",
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
      "rule": "Before binding, logical state role writes and deletes are allowed only after the final read of that same role; bound validation instead compares actual storage in each access context",
      "surface": "workflow.state_needs"
    },
    {
      "name": "workflow_state_storage.write_after_last_read",
      "reason": "relative paths resolve in each access context; normalized paths, symlinks, and existing hardlinks can alias, while the same role may resolve to different files and be valid",
      "related_capabilities": [],
      "related_codes": [
        "validation.workflow.state_storage.write_before_last_read"
      ],
      "related_model_nodes": [],
      "rule": "After binding, write or delete only after the final read of the same actual file, regardless of role, state name, profile, key, or field",
      "surface": "workflow.state_bindings"
    },
    {
      "name": "workflow_state_storage.relevant_identity_required",
      "reason": "validation must precede observations and effects; uncertain context alone does not reject read-only, read-before-write, or known-disjoint access; individual child validation is not a cross-invocation or cross-iteration guarantee, and no new loop mutation ban is added",
      "related_capabilities": [],
      "related_codes": [
        "validation.workflow.state_storage.identity_unresolved"
      ],
      "related_model_nodes": [],
      "rule": "Conservatively reject early only relevant write/later-read pairs whose storage identity cannot be established; this is not a proven ordering violation",
      "surface": "workflow.state_bindings"
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
