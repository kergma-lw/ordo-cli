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
- why a particular step was chosen;
- which playbook-run profile is active;
- which overrides are active.

## Why this matters

For agent-authored workflows, `execute` alone is not enough.

The runtime needs modes that:
- reduce risk;
- improve reviewability;
- provide machine-readable reasoning.

## Runtime ownership of mode semantics

The runtime owns `check`, `plan`, `execute`, `explain`, and future next-safe-action semantics.
Connector operations should not each reimplement those modes locally.

Instead, runtime should derive higher-level execution meaning from structured operation contracts and structured operation outcomes.

Implications:
- connector operations may provide local observations, effect summaries, diagnostics, and supplementary raw detail;
- runtime combines those local results with workflow structure, guard evaluation, profiles, and policy to determine blocked state, plan shape, explanation, and next safe action;
- richer runtime modes should come from stronger structured operation surfaces rather than from pushing orchestration logic down into connector implementations.

## Connector dependency direction

The runtime core should be agnostic to the physical location of built-in connectors.

It should depend on:
- connector registry data for resolution;
- probe and action execution capabilities provided through explicit wiring.

It should not depend on a hardcoded connector package path as part of its core semantics.

## Composition layer

A composition layer such as CLI bootstrap, application bootstrap, or tests may choose which connector provider to install or pass explicitly.

This layer may:
- use the standard built-in connector provider;
- combine the built-in provider with local or project-specific connectors;
- run with no built-in connector provider at all.
