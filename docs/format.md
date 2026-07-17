# Ordo format draft

## Intent

Ordo files describe local workflows as:

1. inputs
2. guards
3. steps
4. execution mode
5. structured outcomes

The format is meant to be authored by both humans and agents.

## Top-level shape

```yaml
version: 0
workflow: string

inputs: {}
state_needs: {}
guards: []
steps: []
```

## Principles

- keep the connector/operation set small
- prefer explicit fields over magic defaults
- keep semantics deterministic
- shell is an escape hatch, not the main abstraction

## Guards

Guards are preconditions without intended side effects.
They may reference public connector operations directly or use a compact boolean expression surface.

Compatibility-only object form:

```yaml
- uses: namespace.name
  with: {}
```

Preferred native form uses expression entries such as `git.repo` directly.

Compact expression form:

```yaml
- git.worktree.clean and git.branch.value != "main"
```

Expression guards are intended for the compact statement of execution policy.
They should answer, briefly and reviewably, whether execution is allowed now.

Each guard item is a separate boolean clause.
The `guards` list combines with implicit `and` semantics across items.
Use `or` inside one expression when a single clause needs disjunction.

Guard-expression rules:

- zero-argument probes do not require `()`;
- parameterized probes prefer named arguments when inputs are supplied;
- field access reads documented probe outputs;
- boolean composition should support at least `and`, `or`, `not`, and parentheses;
- expression guards evaluate only `probe`-level facts, never effectful actions.

Illustrative examples:

```yaml
guards:
  - git.worktree.clean
  - git.branch.value != "main"
  - gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state not in ["DONE", "CLOSED"]
```

Current implementation note:

- the workflow contract and runtime support plain-string guard expressions;
- expression guards resolve only public `probe` operations;
- failed expression guards preserve structured guard details and evaluation traces.

Expected outcome classes:
- pass
- guard_failed
- probe_failed

## Steps

Steps are effectful actions.
They may reference public connector operations or use built-in runtime state mutation forms.

Steps may also declare an optional `if` condition using the preferred bare condition surface.

Illustrative forms:

```yaml
- name: comment-open
  if: step.issue.outputs.open and inputs.notify
  uses: gh.issue.comment
  with:
    issue_id: ${step.issue.outputs.id}
    body: "Issue is open."

- name: remember-branch
  if: (inputs.branch | trim | ne("")) and inputs.persist_branch
  state_set:
    state.task_memory[inputs.task_key].branch: ${inputs.branch}
```

Step-condition rules:

- step conditions use the same boolean composition syntax as guard expressions: `and`, `or`, `not`, and parentheses;
- step conditions read only workflow-local roots such as `inputs...`, `state...`, and prior `step...` results;
- existing value-expression pipelines remain valid leaf forms when they produce boolean values;
- step conditions do not call connector operations or probes.
- the older embedded form `if: ${...}` remains deprecated compatibility surface only.

Minimal shape:

```yaml
- name: some-step
  uses: namespace.name
  with: {}
```

Built-in runtime state mutation forms:

```yaml
- name: remember-branch
  state_set:
    state.task_memory[inputs.task_key].branch: ${inputs.branch}

- name: forget-branch
  state_delete: state.task_memory[inputs.task_key].branch
```

Stable state path grammar:

```text
state.<role>[inputs.<key-reference>][.<field>...]
```

Examples:

- `state.task_memory[inputs.task_key]`
- `state.task_memory[inputs.task_key].branch`
- `state.task_memory[inputs.task_key].metadata.owner`

Initial restrictions:

- reads use this path only inside `${...}`;
- `state_set` keys use the path text directly;
- `state_delete` uses the path text directly;
- `<role>` is a logical workflow state role;
- the bracketed key must use dotted `inputs...` form;
- field traversal after the key uses dotted identifiers only;
- quoted keys, literal keys, repeated bracket segments, and arbitrary nested expressions are not part of the initial stable syntax.

## Value expressions

Workflow values may use `${...}` for pure local value computation.

Illustrative examples:

```yaml
${inputs.title | slug}
${format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug)}
```

When an inline `format(...)` call becomes too dense, the same root form may use a structured YAML equivalent:

```yaml
branch:
  format: "{}/{}-{}"
  args:
    - ${inputs.type | lower}
    - ${inputs.issue_number}
    - ${inputs.title | slug}
```

This YAML form is selective rather than universal. Simple filter pipelines such as `${inputs.title | slug}` stay inline.

## Runtime state

Workflows declare logical state needs, while the playbook declares concrete runtime-managed state locations.

```yaml
state_needs:
  task_memory: {}
```

The initial `state_needs` shape is marker-only.
Each logical role maps to an empty object.
The workflow does not define storage path, backend, or other concrete project state details there.

Playbook-side state declarations look like:

```yaml
states:
  repo_task_state:
    path: .ordo/state/task-state.json
```

The playbook then binds workflow logical roles to concrete state entries.

Step values may read from runtime state through direct references:

```yaml
${state.task_memory[inputs.task_key].branch}
```

Optional later extensions:
- `if`
- `register`
- `retry`
- `on_fail`

## Modes

Planned runtime modes:
- `check`
- `plan`
- `execute`
- `explain`

## Minimal semantics

- all guards are evaluated before steps
- any failed guard stops execution
- steps run in declared order
- unknown fields should fail validation
- unknown connector operations should fail at runtime resolution
