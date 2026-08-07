# Workflow step conditions

## Role

Step conditions provide a compact workflow-owned step eligibility and admission surface.

They exist so one declared step may either:

- execute only when a local runtime-visible predicate evaluates to `true`; or
- fail closed before execution when a late admission predicate does not pass.

They do not introduce first-class branch blocks, loops, or join semantics.

## Authoring surface

Any workflow step form may declare an optional `if` field.

Any workflow step form may also declare an optional `gate` field.

Illustrative forms:

```yaml
steps:
  - name: inspect-issue
    uses: gh.issue
    with:
      repository: inputs.repository
      issue_number: inputs.issue_number
    register: issue

  - name: comment-open
    if: step.issue.outputs.open
    uses: gh.issue.comment
    with:
      issue_id: step.issue.outputs.id
      body: "Issue is open."

  - name: remember-branch
    if: inputs.persist_branch
    state_set:
      state.task_memory[inputs.task_key].branch: ${inputs.branch}

  - name: announce-story-readiness
    if:
      - step.has_acceptance.outputs.value
      - step.has_tasks_section.outputs.value
      - step.has_minimum_task_count.outputs.value
    uses: gh.issue.comment
    with:
      issue_id: step.story.outputs.id
      body: "Story is ready for review."

  - name: set-story-status-ready
    gate:
      all:
        - step.has_acceptance.outputs.value
        - step.has_tasks_section.outputs.value
        - step.has_minimum_task_count.outputs.value
        - any:
            - step.has_no_linked_stories.outputs.value
            - step.has_no_linked_epics.outputs.value
    uses: gh.project.issue.field_single_select.set
    with:
      issue_id: step.story.outputs.id
      field_name: Status
      option_name: Ready
```

The preferred `if` surface is native and may be authored either as a bare condition expression or as a structured condition block.

The preferred `gate` surface is native and may be authored either as a bare condition expression or as a structured condition block.

Both forms are equal-authority workflow surfaces.

A list-form `if` means implicit `all`.

A list-form `gate` means implicit `all`.

An object-form `if` may express explicit `all`, `any`, or `not` composition and may nest those nodes.

An object-form `gate` may express explicit `all`, `any`, or `not` composition and may nest those nodes.

The older embedded form `if: ${...}` remains available only as deprecated compatibility surface.

The older embedded form `gate: ${...}` remains available only as deprecated compatibility surface.

Within that envelope, step conditions may use limited boolean composition such as `and`, `or`, `not`, and grouped subexpressions in expression form, or `all`, `any`, and `not` in structured form.

## Expression boundary

The `if` and `gate` fields host workflow step-condition semantics whether authored as one expression or as a structured condition tree.

The initial readable roots are:

- `inputs...`
- `state...`
- `step...` for prior registered step results only

Each condition leaf may evaluate predicates and must contribute to one final boolean value.

For `gate`, those readable roots still exclude outputs of the current protected step itself.

It must not invoke connectors or probes and must not choose between alternative values or subexpressions based on a runtime condition.

This keeps step conditions in the local workflow data domain even when they share boolean syntax with guard expressions.

## Boolean discipline

- The final `if` result must be boolean.
- The final `gate` result must be boolean.
- Step conditions may combine boolean-valued subexpressions with `and`, `or`, `not`, and parentheses.
- Step conditions may also combine boolean-valued child conditions with structured `all`, `any`, and `not` nodes.
- A direct reference is valid only when it resolves to boolean.
- Predicate helpers such as equality comparison may be used when they return boolean.
- Existing value-expression pipelines remain valid leaf forms when they produce boolean values.
- Expression `not` is boolean-only.
- Structured `not` is boolean-only and takes exactly one child condition.

Condition evaluation failure in either expression or structured form is a runtime error, not an implicit `false`.

## Skip semantics

When `if` evaluates to `false`, the step is skipped rather than executed.

This outcome is distinct from:

- guard blocking before step execution;
- validation or resolution failure before execution;
- execution failure after a step begins running.

The runtime should preserve machine-usable visibility that a step was skipped because its condition evaluated to `false`.

## Gate semantics

When `gate` evaluates to `false`, the step is blocked rather than executed.

This outcome is distinct from:

- guard blocking before the step sequence is reached;
- `if`-driven skip because the step was not applicable;
- validation or resolution failure before execution;
- execution failure after the step begins running.

The runtime should preserve machine-usable visibility that a step was blocked because its `gate` condition evaluated to `false`.

When one step declares both `if` and `gate`, runtime evaluates `if` first.
If `if` is `false`, runtime skips the step and does not evaluate `gate`.
If `if` is `true`, runtime evaluates `gate` immediately before step execution.

## MVP restriction with register

The MVP does not allow one step to declare both `if` and `register`.

This keeps registered step results tied to actually executed operation-call or value steps and avoids publishing synthetic results for skipped steps.

This restriction does not by itself apply to `gate` because a gate-blocked step does not produce a synthetic successful step result; it simply does not execute.
