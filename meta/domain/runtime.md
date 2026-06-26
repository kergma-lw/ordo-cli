# Runtime domain

## Baseline modes

### `check`

Checks guards and static prerequisites.
It must not execute effectful business steps.

### `plan`

Builds an explainable plan:
- what will be checked;
- which steps are expected;
- where execution is blocked.

### `execute`

Executes the workflow.

### `explain`

Returns an explanation of the runtime decision:
- why a guard failed;
- why a particular step or profile was chosen;
- which overrides are active.

## Why this matters

For agent-authored workflows, `execute` alone is not enough.

The runtime needs modes that:
- reduce risk;
- improve reviewability;
- provide machine-readable reasoning.
