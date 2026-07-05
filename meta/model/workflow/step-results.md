# Workflow step result registration

## Role

Step result registration provides execution-local cross-step data flow.

It exists so a workflow may reuse structured outputs from an earlier step without promoting those values into persistent runtime state.

## Authoring surface

An operation-call step may declare an optional `register` field.

Illustrative form:

```yaml
steps:
  - name: inspect-issue
    uses: gh.issue
    with:
      repository: ${inputs.repository}
      issue_number: ${inputs.issue_number}
    register: issue

  - name: comment
    uses: gh.issue.comment
    with:
      issue_id: ${step.issue.outputs.id}
      body: "Looks good."
```

The `register` value is a workflow-local identifier for that step result.

It is not derived from `name`, and it must not be treated as a human-readable step label.

## Published read surface

The initial read surface for a registered step result is:

- `step.<register>.status`
- `step.<register>.summary`
- `step.<register>.outputs...`

Examples:

- `${step.issue.status}`
- `${step.issue.summary}`
- `${step.issue.outputs.id}`
- `${step.issue.outputs.repository.nameWithOwner}`

The `outputs` subtree is the workflow-facing projection of the structured operation result outputs.

## Boundary

Registered step results are:

- execution-local;
- scoped to one workflow run;
- produced by ordered step execution;
- separate from persistent `state...` values.

Registered step results are not:

- playbook state declarations;
- persistent memory across runs;
- a substitute for guard evaluation;
- an invitation to widen value expressions into a general workflow programming language.

## Order discipline

- A `step.<register>...` reference may target only an earlier step in the same workflow.
- Forward references are invalid.
- Register names must be unique within the workflow.
- Missing register references are invalid.

## Step-form restrictions

- The MVP `register` field belongs only to operation-call steps that use `uses`.
- A step that declares `if` must not also declare `register` in the MVP.
- `state_set` and `state_delete` do not publish registered step results in the MVP.
- A probe operation used as a normal step may declare `register` like any other operation-call step.

## Guard boundary

Registered step results do not participate in guard evaluation.

Guard expressions may read workflow inputs and public probe results, but not `step...` values.
Interleaved guard blocks therefore remain a policy barrier over observable workflow state rather than over registered step-result memory.
