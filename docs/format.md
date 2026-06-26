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
- git.worktree.clean and git.branch != "main"
```

Expression guards are intended for the compact statement of execution policy.
They should answer, briefly and reviewably, whether execution is allowed now.

Each guard item is a separate boolean clause.
The `guards` list combines with implicit `and` semantics across items.
Use `or` inside one expression when a single clause needs disjunction.

Current draft direction for guard expressions:

- zero-argument probes do not require `()`;
- parameterized probes use arguments only when needed;
- field access reads documented probe outputs;
- boolean composition should support at least `and`, `or`, `not`, and parentheses;
- expression guards evaluate only `probe`-level facts, never effectful actions.

Illustrative examples:

```yaml
guards:
  - git.worktree.clean
  - git.branch != "main"
  - gh.issue(${inputs.issue}).project.member
  - gh.issue(${inputs.issue}).status not in ["Done", "In review"]
```

Draft implementation note:

- the workflow contract and schema now admit plain-string expression guards;
- runtime parsing and evaluation of guard expressions is not yet implemented in the current v0 foundation.

Expected result:
- pass
- fail
- error

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
