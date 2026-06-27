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

Operation-call form:

```yaml
- uses: namespace.name
  with: {}
```

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
  - gh.issue(issue=inputs.issue).project.member
  - gh.issue(issue=inputs.issue).status not in ["OPEN", "CLOSED"]
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
They reference public connector operations.

Minimal shape:

```yaml
- name: some-step
  uses: namespace.name
  with: {}
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
