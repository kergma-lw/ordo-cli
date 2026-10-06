# Step admission runtime model

## Role

Step admission introduces one runtime-visible control point between:

- reaching a step in ordered workflow execution; and
- actually dispatching that step.

It exists to model readiness and late admission checks that should fail honestly rather than disappear as optional routing.

## Semantic split

- `guards` answer whether workflow execution may cross an earlier workflow barrier.
- `if` answers whether a particular step is applicable and should be skipped when false.
- `gate` answers whether a reached step is admitted to execution and should fail when false.
- Across all three condition surfaces, failed read-only observation is evaluation failure rather than boolean `false`.

This distinction is semantic, not only diagnostic.

## Evaluation order

For one step, the runtime order is:

1. resolve the step shape and dependencies;
2. evaluate `if` when present;
3. if `if` is `false`, mark the step skipped and stop evaluation for that step;
4. evaluate `gate` when present;
5. if `gate` is `false`, mark the step gate-blocked and fail the workflow;
6. otherwise execute the step normally.

`gate` is therefore a late admission boundary, not an alternate skip surface.

## Typical use

`gate` is most valuable when:

- earlier steps established read-only observations;
- the protected step is effectful or mutating;
- failing readiness should be surfaced as an actionable workflow failure.

Illustrative shape:

```yaml
- name: Set story status to Ready
  uses: gh.project.issue.field_single_select.set
  gate:
    all:
      - step.has_acceptance.outputs.value
      - step.has_tasks_section.outputs.value
      - step.has_minimum_task_count.outputs.value
      - step.all_linked_items_ready.outputs.value
      - step.has_no_linked_stories.outputs.value
      - step.has_no_linked_epics.outputs.value
```

## Truth model

Runtime-facing admission analysis should preserve more than one flat boolean when possible.

Useful clause-level states are:

- `passed`;
- `failed`;
- `unknown`.

This matters especially for `check` and `explain`.

Recommended mode interpretation:

- `execute`: `unknown` is conservative and must not authorize step execution;
- `check`: `unknown` remains explicit rather than upgraded into allowed;
- `explain`: `unknown` should remain attributable to the exact missing or unobserved clause.

## Outcome distinctions

Runtime should preserve the distinction between:

- skipped because `if` was false;
- blocked because `gate` was false;
- failed because `gate` could not be evaluated safely;
- failed because step execution itself failed after admission.

Even if public workflow status still collapses the last three cases to workflow failure, the step-level outcome should remain distinguishable.

## Preflight interaction

`check` may strengthen gate analysis through the preflight step interpreter defined in `meta/model/runtime/preflight-step-interpreter.md`.

That means `check` may:

- execute relevant read-only probe steps;
- evaluate pure value steps;
- materialize prior read-only `step...` facts;
- decide whether a later gated step can be admitted.

That does not allow `check` to execute the gated effectful step itself.

The same admission semantics should survive structural nesting.

If one `gate` surface is observation-capable at top level, the runtime model should preserve that same approved dependency class inside nested inline `steps`, inline `for_each` bodies, and reusable fragment bodies rather than introducing narrower ad hoc local-only variants.

## Projection expectations

### `run`

- Preserve gate evaluation in the execution trace.
- Preserve which gate clauses failed when available.
- Fail on the protected step without dispatching it.

### `check`

- Report `can run`, `cannot run`, or honest incompleteness for a gated step.
- Preserve clause-level `passed`, `failed`, and `unknown` detail when available.

### `plan`

- Show that prerequisite read-only observations happen before gate evaluation.
- Show that the protected step executes only if admission succeeds.

### `explain`

- Explain gate blocking distinctly from skip and generic execution failure.
- Preserve structured condition shape closely enough to explain nested `all`, `any`, and `not` reasoning.

## Authoring guidance

Prefer structured `gate` form when a step has multiple readiness clauses.

Preferred:

```yaml
gate:
  all:
    - step.a.outputs.value
    - step.b.outputs.value
```

Discouraged:

```yaml
gate: step.a.outputs.value and step.b.outputs.value and step.c.outputs.value
```

Structured form keeps admission analysis easier to review, explain, and project across runtime modes.

## Failure-focused diagnostic context

Structured `gate` objects may also include an optional `on_fail` mapping.

Illustrative shape:

```yaml
gate:
  all:
    - step.project_issue.outputs.exists
    - step.project_issue.outputs.status | eq("Ready")
  on_fail:
    repository: step.repository.outputs.value
    issue_number: step.issue_number.outputs.value
    status: step.project_issue.outputs.status
```

Semantics:

- `gate` still owns the admission verdict;
- `on_fail` does not participate in pass/fail logic;
- runtime evaluates `on_fail` only when the gate verdict is `failed`;
- evaluated entries become compact machine-readable failure context for `run`, `check --json`, and `explain`;
- gate-failure diagnostics should prefer this compact context and should not emit broad visible-register dumps.

`on_fail` entries use the same step-local read-only authoring context as the gate itself.
