# Workflow-authoring feature map

Choose the narrowest published authoring surface that expresses the intended workflow behavior.

Use the clusters to choose a surface, then follow their published handles for details.

## Read a named surface

- Each handle in this map has a focused guide: run `ordo-help describe <handle>` after choosing a surface.
- Choose include for source-level fragment reuse, run for a later fragment invocation or bounded repeated work, and profile switch when later work needs another declared profile.
- Use playbook workflows to publish named workflows with shared defaults or pre-run preparation before the requested workflow starts.
- Profiles can publish input defaults, explicit overrides, and legacy launchers; overrides are metadata, while launchers are compatibility-only setup for older workflows.

## Feature clusters



### Playbook

Project-local catalog for named workflows and launch context.



#### Public names

- top level fields: version, pre_run, states, defaults, connectors, workflows, profiles
- workflow entry fields: file, with, description, category, when, working_directory, state_bindings
- pre run entry fields: file, with, state_bindings
- defaults fields: profile, working_directory

### Profile

Reusable project execution context for stable defaults.



#### Public names

- top level fields: name, inputs, working_directory, connectors, checks, overrides, launchers
- override fields: target, with, reason
- deprecated launcher fields: file, connector, before, after

### Workflow

An executable workflow with explicit inputs, guards, steps, and outputs.



#### Public names

- top level fields: version, workflow, profile, inputs, let, state_needs, blocks
- block forms: guard_block, step_block, include_block
- step forms: operation_call, run_invocation, inline_fan_out_invocation, profile_switch, value, result, publish, state_set, state_delete, gate_checkpoint
- step fields: name, uses, if, gate, with, register, launcher, run, for_each, steps, profile_switch, value, result, publish, state_set, state_delete
- profile switch step forms: profile_switch

### State

Durable coordination data shared by related workflow stages.



#### Public names

- workflow surface: state_needs, state_bindings, states, state_set, state_delete
- path root: state
- path shape: state.<role>[<expression>][.<field>...]

### Include

Reusable source fragments with explicit arguments.



#### Public names

- call fields: include, with
- fragment metadata fields: description, args
- fragment argument forms: required_short_form, object_form

### Run

Runtime invocation for reusable fragments and bounded repeated work.



#### Public names

- call fields: run, steps, if, gate, with, for_each, register
- body forms: named_run_target, inline_repeated_steps
- step forms: run_invocation, inline_fan_out_invocation
- fan out fields: item_binding, outer_if_scope, inner_if_scope, outer_register_scope

### Guards

Early workflow applicability and input validation.



#### Public names

- workflow fields: guards
- guard forms: operation_call, expression
- allowed roots: inputs, probe, state
- allowed filters: lower, trim, slug, eq, ne, not, is_string, is_number, is_integer, is_boolean, in, field, lookup, only, flatten, first, last, length, unique, catch, not_found
- allowed builtins: format, is_missing, is_present

### Gates

Admission control for a path inside an already-applicable workflow.



#### Public names

- step field: gate
- step forms: operation_call, run_invocation, inline_fan_out_invocation, profile_switch, value, result, publish, state_set, state_delete, gate_checkpoint
- structured operators: all, any, not
- structured optional fields: on_fail

### Conditions

Readable boolean decisions for local branching and admission.



#### Public names

- condition fields: let, guards, if, gate
- structured operators: all, any, not
- list semantics: implicit_all
- boolean operators: and, or, not, parentheses

### Local Expressions

Short workflow-local reads, checks, comparisons, and transformations.



#### Public names

- roots: args, inputs, probe, state, step
- filters: lower, trim, slug, eq, ne, not, is_string, is_number, is_integer, is_boolean, in, field, lookup, only, flatten, first, last, length, unique, catch, not_found
- builtins: format, is_missing, is_present
- structured condition operators: all, any, not
- comparison operators: ==, !=, in, not in

### Connectors

Published operations for observing or changing systems, or for narrowly scoped current-run work.



#### Public names

- namespaces: runtime, git, compose, gh, shell, fs

### Routines

A limited project-local helper path.



#### Public names

- top level fields: version, routines
- routine entry fields: kind, summary, args, implementation, failure_modes, outputs, log_hints
- workflow call fields: args, env
- implementation fields: argv

### Adapters

Structured representations for clearer workflow decisions and results.



#### Public names

- families: json, key_value, markdown, text, yaml
- json: field, many, one, remove, set
- markdown: add, append, blocks, list, list_items, lists, paragraph, paragraphs, prelude, remove, replace, task_list, task_list_items, task_lists
- text: after, append, before, find, finds, lines, remove, replace
- yaml: field, many, one

## Decision boundary

- Use a direct published surface first.
- Compose published surfaces when they fit cleanly.
- Treat a remaining semantic gap as a reason to clarify, not a reason to improvise a fallback.
