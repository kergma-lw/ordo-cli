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
They reference public connector operations.

Minimal shape:

```yaml
- uses: namespace.name
  with: {}
```

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
