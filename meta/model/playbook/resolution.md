# Playbook resolution model

## Resolution base

Resolution starts from the directory that contains the discovered playbook file.

For the canonical default path:

```text
<project>/.ordo/ordo.yaml
```

the resolution base is:

```text
<project>/.ordo/
```

## Named workflow resolution

When CLI is asked to run a named workflow entry such as `close-task`, it resolves that name through `workflows.<name>` in the playbook.

The entry must resolve to exactly one workflow file.

## Pre-run workflow resolution

- `pre_run` is an optional ordered list of playbook-owned launch-phase entries declared directly on the playbook.
- Each `pre_run` item must declare its workflow `file` explicitly.
- Each `pre_run` item resolves its `file` with the same workflow-path rules as a named workflow file reference.
- Each `pre_run` item may declare launch-phase `state_bindings` that apply only while that `pre_run` workflow is being evaluated.
- `pre_run` workflows execute in declaration order before the requested workflow performs its own effectful execution.
- `pre_run` workflows run in the same runtime session as the requested workflow.
- Runtime context changes produced by `pre_run` workflows may affect later `pre_run` items and the requested workflow.
- Failure in a `pre_run` workflow prevents effectful execution of the requested workflow.
- `pre_run` state dependencies must not require the requested workflow to widen its own declared logical state contract.

## Workflow file resolution

- A bare workflow filename such as `close-task.yml` resolves under `<playbook-dir>/workflows/`.
- A relative workflow path containing directory segments resolves relative to `<playbook-dir>/`.
- An absolute workflow path remains absolute.

## Profile reference resolution

- A bare named profile reference such as `backend-default` resolves through `profiles.<name>` in the playbook.
- A bare profile filename such as `backend-default.yml` resolves under `<playbook-dir>/profiles/`.
- A relative profile path containing directory segments resolves relative to `<playbook-dir>/`.
- An absolute profile path remains absolute.

## Active profile resolution

- Each playbook run selects at most one active profile.
- If the caller specifies a profile explicitly, that selection wins.
- Otherwise `defaults.profile` becomes the active profile when present.
- If no explicit profile and no default profile are present, the run proceeds without a profile.
- Active profile resolution happens before workflow activation and step execution.
- The profile selected by activation is the starting profile for any `pre_run` workflows and for the requested workflow.

## Execution working directory

- Playbook `defaults.working_directory`, active-profile `working_directory`, and workflow-entry `working_directory` are the three explicit declaration surfaces for execution working directory.
- When more than one declaration is present, the resolved working directory follows increasing specificity in this order: playbook defaults, then active profile, then active workflow entry.
- Each `working_directory` value may be either a literal path string or a `${...}` embedded-value local expression that resolves to a path string.
- A `working_directory` expression reuses the existing embedded-value local-expression surface but with a narrower activation-time subset.
- The activation-time surface may read only launch-known input values.
- The activation-time surface must not read `state...`, `step...`, or any other runtime-derived value.
- The activation-time surface must resolve fully before the first guard or step executes.
- After expression evaluation, a relative `working_directory` path resolves relative to `<playbook-dir>/`, regardless of whether it originated from playbook defaults, the active profile, or the workflow entry.
- After expression evaluation, an absolute `working_directory` path remains absolute.
- When present, runtime executes the workflow with that resolved working directory as the execution working directory.
- Runtime may restore its prior process working directory after the run completes, but that restoration behavior must not be part of workflow semantics.
- `working_directory` changes execution context only; it must not change playbook discovery, workflow/profile reference resolution, or state-path resolution.

## Launch-time input overrides

- A playbook run may accept explicit launch-time input overrides from the caller.
- Launch-time input overrides apply to the selected workflow run only.
- Launch-time input overrides take precedence over workflow-declared input defaults.
- Launch-time input overrides also take precedence over profile-provided missing-input defaults.
- A launch-time input override may be provided either inline or from a file-backed raw string value.
- Launch-time input overrides do not mutate the playbook, workflow source file, or profile source file.

## State resolution

- Playbook state names resolve through `states.<name>`.
- A relative state `path` resolves relative to `<playbook-dir>/`.
- An absolute state `path` remains absolute.

## Workflow state binding resolution

- Workflow state reads and writes address logical roles through `state.<role>...`.
- The active workflow entry resolves those logical roles through `state_bindings.<role>`.
- Each bound value must resolve to one declared playbook state entry.
- Every workflow-declared logical state role must resolve through `state_bindings.<role>`.
- Missing state bindings fail before effectful workflow execution begins.
- Extra state bindings that do not correspond to declared workflow logical state roles fail validation.

## Resolution discipline

- Resolution must be deterministic.
- Ambiguous implicit matches are not allowed.
- Playbook resolution must complete before effectful workflow execution begins.
