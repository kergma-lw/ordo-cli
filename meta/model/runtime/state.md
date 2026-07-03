# Runtime state model

## Position

Runtime state is a built-in runtime capability for small persistent workflow-owned values.

It is not:

- a connector family;
- a replacement for external source-of-truth systems;
- a general-purpose memory subsystem in the initial model.

## Top-level declaration

Workflows may declare named runtime state locations through a top-level `states` mapping.

Minimal shape:

```yaml
states:
  task_state: .ordo/task-state.json
```

The initial model treats the declared value as a runtime-managed location identifier. The first backend may be file-backed.

## Mutation step forms

State mutation uses dedicated built-in step forms rather than connector `uses` references.

Set example:

```yaml
steps:
  - name: remember-branch
    state_set:
      states.task_state[inputs.issue_ref].branch: ${inputs.branch}
```

Delete example:

```yaml
steps:
  - name: forget-branch
    state_delete: states.task_state[inputs.issue_ref].branch
```

These forms are effectful runtime operations even though they do not go through the public connector registry.

## Read surface

State reads use direct references instead of a dedicated retrieval step.

Illustrative form:

```yaml
${states.task_state[inputs.issue_ref].branch}
```

The read surface should stay aligned with the mutation target surface so that authors do not learn two unrelated addressing models.

## MVP constraints

- The initial model should remain centered on named state locations and addressed values.
- The initial model should not assume multiple state scopes beyond explicitly declared named entries.
- The initial model should not require bulk update semantics, query semantics, or concurrency semantics.
- The initial model should not rename this capability into a larger semantic system before the runtime actually owns those broader concerns.
