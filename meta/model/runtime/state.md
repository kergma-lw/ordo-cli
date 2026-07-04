# Runtime state model

## Position

Runtime state is a built-in runtime capability for small persistent workflow-owned values.

Its declaration point belongs to playbook-level project orchestration context rather than to individual workflow files.

It is not:

- a connector family;
- a replacement for external source-of-truth systems;
- a general-purpose memory subsystem in the initial model.

## Top-level declaration

Playbooks may declare named runtime state locations through a top-level `states` mapping.

Minimal shape:

```yaml
states:
  repo_task_state:
    path: .ordo/state/task-state.json
```

The initial model treats the declared value as a runtime-managed location identifier. The first backend may be file-backed.

Workflow files consume logical state roles through `state.<role>...` references and state mutation step forms.
The playbook binds those logical roles to declared project state entries.
If a workflow declares a logical state role, activation requires a corresponding playbook binding.

The initial `state_needs` contract is marker-only.
It declares that a workflow needs a named logical role such as `task_memory`,
but it does not yet add per-need schema, purpose, kind, or capability subfields.

Illustrative binding shape:

```yaml
workflows:
  close-task:
    file: close-task.yml
    state_bindings:
      task_memory: repo_task_state
```

## Mutation step forms

State mutation uses dedicated built-in step forms rather than connector `uses` references.

Set example:

```yaml
state_needs:
  task_memory: {}

steps:
  - name: remember-branch
    state_set:
      state.task_memory[inputs.issue_ref].branch: ${inputs.branch}
```

Delete example:

```yaml
steps:
  - name: forget-branch
    state_delete: state.task_memory[inputs.issue_ref].branch
```

These forms are effectful runtime operations even though they do not go through the public connector registry.

## Read surface

State reads use direct references instead of a dedicated retrieval step.

Illustrative form:

```yaml
${state.task_memory[inputs.issue_ref].branch}
```

The read surface should stay aligned with the mutation target surface so that authors do not learn two unrelated addressing models.

## Stable path grammar

The initial stable state path grammar is:

```text
state.<role>[inputs.<key-reference>][.<field>...]
```

Examples:

- `state.task_memory[inputs.issue_ref]`
- `state.task_memory[inputs.issue_ref].branch`
- `state.task_memory[inputs.issue_ref].metadata.owner`

Read usage wraps the same path inside a value expression:

```yaml
${state.task_memory[inputs.issue_ref].branch}
```

Mutation targets use the same path text directly:

```yaml
state_set:
  state.task_memory[inputs.issue_ref].branch: ${inputs.branch}

state_delete: state.task_memory[inputs.issue_ref].branch
```

## Initial grammar restrictions

- the path must start with `state.`;
- `<role>` is an identifier-like logical state role name;
- the bracketed key reference must use dotted `inputs...` form;
- at least one segment must follow `inputs` inside the key reference;
- field traversal after the key is optional and uses dotted identifiers only;
- the initial grammar does not support literal keys, quoted keys, multiple bracket segments, arbitrary nested expressions, or mixed index syntaxes.

## MVP constraints

- The initial model should remain centered on named state locations and addressed values.
- State declaration ownership should remain at playbook level so workflows do not duplicate project-local storage setup.
- Workflow authoring should use logical state roles rather than concrete project state instance names.
- A declared workflow logical state role is a required composition dependency rather than an optional hint.
- The initial state-need contract should stay marker-only until runtime owns a clear reason for richer per-need fields.
- The initial model should not assume multiple state scopes beyond explicitly declared named entries.
- The initial model should not require bulk update semantics, query semantics, or concurrency semantics.
- The initial model should not rename this capability into a larger semantic system before the runtime actually owns those broader concerns.
