# Workflow step conditions

## Role

Step conditions provide a compact workflow-owned step eligibility surface.

They exist so one declared step may execute only when a local runtime-visible predicate evaluates to `true`.

They do not introduce first-class branch blocks, loops, or join semantics.

## Authoring surface

Any workflow step form may declare an optional `if` field.

Illustrative forms:

```yaml
steps:
  - name: inspect-issue
    uses: gh.issue
    with:
      repository: ${inputs.repository}
      issue_number: ${inputs.issue_number}
    register: issue

  - name: comment-open
    if: ${step.issue.outputs.open}
    uses: gh.issue.comment
    with:
      issue_id: ${step.issue.outputs.id}
      body: "Issue is open."

  - name: remember-branch
    if: ${inputs.persist_branch}
    state_set:
      state.task_memory[inputs.task_key].branch: ${inputs.branch}
```

The initial `if` surface uses the existing string-form value-expression envelope `if: ${...}`.

## Expression boundary

The `if` field hosts value expressions with workflow step-condition semantics.

The initial readable roots are:

- `inputs...`
- `state...`
- `step...` for prior registered step results only

The expression may evaluate predicates and return a boolean value.

It must not invoke connectors or probes and must not choose between alternative values or subexpressions based on a runtime condition.

## Boolean discipline

- The final `if` result must be boolean.
- A direct reference is valid only when it resolves to boolean.
- Predicate helpers such as equality comparison may be used when they return boolean.
- `not` is boolean-only.

Condition evaluation failure is a runtime error, not an implicit `false`.

## Skip semantics

When `if` evaluates to `false`, the step is skipped rather than executed.

This outcome is distinct from:

- guard blocking before step execution;
- validation or resolution failure before execution;
- execution failure after a step begins running.

The runtime should preserve machine-usable visibility that a step was skipped because its condition evaluated to `false`.

## MVP restriction with register

The MVP does not allow one step to declare both `if` and `register`.

This keeps registered step results tied to actually executed operation-call steps and avoids publishing synthetic results for skipped steps.
