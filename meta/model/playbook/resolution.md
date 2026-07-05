# Playbook resolution model

## Resolution base

Resolution starts from the directory that contains the discovered playbook file.

For the canonical default path:

```text
<project>/.ordo/playbook.yml
```

the resolution base is:

```text
<project>/.ordo/
```

## Named workflow resolution

When CLI is asked to run a named workflow entry such as `close-task`, it resolves that name through `workflows.<name>` in the playbook.

The entry must resolve to exactly one workflow file.

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

## Execution working directory

- A workflow entry may declare `working_directory` as explicit runtime context for runs of that entry.
- `working_directory` may be either a literal path string or a `${...}` value expression that resolves to a path string.
- A `working_directory` expression reuses the existing value-expression syntax but with a narrower activation-time surface.
- The activation-time surface may read only launch-known input values.
- The activation-time surface must not read `state...`, `step...`, or any other runtime-derived value.
- The activation-time surface must resolve fully before the first guard or step executes.
- After expression evaluation, a relative `working_directory` path resolves relative to `<playbook-dir>/`.
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
