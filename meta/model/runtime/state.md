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
      state.task_memory[inputs.task_key].branch: ${inputs.branch}
```

Delete example:

```yaml
steps:
  - name: forget-branch
    state_delete: state.task_memory[inputs.task_key].branch
```

These forms are effectful runtime operations even though they do not go through the public connector registry.

## Read surface

State reads use direct references instead of a dedicated retrieval step.

Illustrative form:

```yaml
${state.task_memory[inputs.task_key].branch}
```

The read surface should stay aligned with the mutation target surface so that authors do not learn two unrelated addressing models.

## Missing-value diagnostic reporting

Aggregate runtime diagnostics group only emitted `runtime.value.state_missing`
events with the same private resolved target: the runtime-resolved absolute
location path, scalar key converted to text, and field path. Logical roles and
state declaration names do not separate an otherwise identical target. This is
conservative path identity, not inode or symlink identity, and is distinct from
the bound write-order validation identity below. The private target is not
serialized. Other errors and missing-state diagnostics without that identity
remain ungrouped.

A singleton keeps its existing diagnostic path and details. A repeated target
retains the first event's details and adds `occurrence_count` and `reported_at`.
The count measures emitted failure events, not inferred reads or unique sites.
`reported_at` lists only the unique locations where diagnostic events were
actually emitted during this evaluation, not all dependent uses of the value.
Each site has a unique effective structural `path` and a `references` list of
distinct `{expression, state}` pairs from those events. Paths describe the
effective assembled structure, including caller prefixes for child sites, not
source line numbers; sites do not carry a separate workflow field. Repeated
events at one site increase the count without duplicating the site or reference.
The diagnostic retains that path for one site and uses an empty path for multiple
sites. Groups, sites, and references retain first-seen order.

This is aggregate reporting only: `check`, `review`, `plan`, `run`, and `explain`
retain their evaluation order, short-circuiting, cache behavior, statuses, and
barriers. Grouping does not evaluate skipped expressions or read state again.
Operation-result diagnostics remain unchanged. `next` retains each candidate's
grouped check diagnostics locally, without merging across candidates or changing
eligibility or selection.

## Stable path grammar

The initial stable state path grammar is:

```text
state.<role>[<expression>][.<field>...]
```

Examples:

- `state.task_memory[inputs.task_key]`
- `state.task_memory[inputs.task_key].branch`
- `state.task_memory[inputs.task_key].metadata.owner`

Read usage wraps the same path inside a value expression:

```yaml
${state.task_memory[inputs.task_key].branch}
```

Mutation targets use the same path text directly:

```yaml
state_set:
  state.task_memory[inputs.task_key].branch: ${inputs.branch}

state_delete: state.task_memory[inputs.task_key].branch
```

## Initial grammar restrictions

- the path must start with `state.`;
- `<role>` is an identifier-like logical state role name;
- the bracketed key must be a valid runtime local expression;
- the bracketed key expression must resolve to a non-null scalar value;
- field traversal after the key is optional and uses dotted identifiers only;
- the initial grammar does not support multiple bracket segments or mixed index syntaxes after the key expression.

## MVP constraints

- The initial model should remain centered on named state locations and addressed values.
- State declaration ownership should remain at playbook level so workflows do not duplicate project-local storage setup.
- Workflow authoring should use logical state roles rather than concrete project state instance names.
- A declared workflow logical state role is a required composition dependency rather than an optional hint.
- The initial state-need contract should stay marker-only until runtime owns a clear reason for richer per-need fields.
- The initial model should not assume multiple state scopes beyond explicitly declared named entries.
- The initial model should not require bulk update semantics, query semantics, or concurrency semantics.
- The initial model should not rename this capability into a larger semantic system before the runtime actually owns those broader concerns.
- The initial model should treat runtime state as persistent handoff memory across runs, not as a second per-run scratch surface beside step registers.
- State writes and deletes belong to the top-level workflow authoring surface rather than to include fragments or run-invoked fragments.
- Within one workflow, an actual state storage file must be written or deleted only after its final read, regardless of logical role, declared state name, profile, key, or field.

## Validation stages and storage identity

Unbound authoring validation retains the role-wide final-read rule and reports
`validation.workflow.state_role.write_before_last_read`. Once bindings are
available, comparison uses actual storage identity in each access context, not
role equality. The same role can therefore write one file and later read a
different file after a context switch without violating this rule.

Relative paths retain their runtime access-context resolution. Already absolute
locations, including locations resolved by playbook activation, remain absolute;
validation does not introduce a new global path base. Normalized paths, symlink
aliases, and existing hardlinks to the same file count as the same storage.
Profile names or different declaration names do not separate aliases.

`validation.workflow.state_storage.write_before_last_read` reports a proven
write/delete before a later read of the same actual file.
`validation.workflow.state_storage.identity_unresolved` is conservative early
rejection of a relevant write/later-read pair whose storage identity cannot be
established without execution or observations, including differing access
contexts across modes. It is not a proven ordering violation. Known-disjoint
storage, read-only access, and read-before-write order are not rejected merely
because some context is uncertain.

Reads within a mutating step precede its mutation. Validation examines authored
order within each validated workflow before observations or effects. Named
children are validated individually, not flattened into the caller's access
stream. Cross-invocation guarantees and cross-iteration analysis are explicitly
deferred, with no new ban on loop mutation and no claim of full composed-run or
cross-run safety proof.

Top-level preflight may defer validated state mutations and continue to later
independent guards without mutating or simulating storage. Nested analysis does
not defer them; a reached invocation or loop after deferral is an analysis barrier.
See `check-semantics.md` and `preflight-step-interpreter.md` for that boundary and
`lifecycle.md` for retention and non-reuse of deferred nodes during planning and execution.
