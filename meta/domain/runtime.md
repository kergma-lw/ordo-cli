# Runtime domain

## Baseline modes

Baseline modes are distinct runtime questions, not necessarily wholly separate evaluation pipelines.
They may share observations, diagnostics, and blocked-state facts, but they differ in primary intent.

Detailed `check` rules live in `meta/model/runtime/check-semantics.md`.

### `check`

Answers whether execution may proceed safely.

It evaluates guard blocks and static prerequisites.
It must not execute effectful business steps.

Its primary value is a safe preflight verdict:
- whether execution is allowed or blocked;
- which guards or prerequisites failed;
- which immediate blockers must be resolved first.

That verdict must remain honest about coverage and incompleteness as defined in `meta/model/runtime/check-semantics.md`.

### `plan`

Answers what execution shape is expected.

It builds an explainable plan that shows:
- what will be checked block by block;
- which step blocks are expected to become executable;
- which steps are expected in each step block;
- where execution is blocked.

Its primary value is execution preview, not merely blocked-versus-allowed status.

### `execute`

Executes the workflow.

### `explain`

Answers why the runtime reached its current decision.

It returns an explanation of the current runtime decision state, not only of completed execution:
- why execution is blocked or allowed;
- why a guard block failed;
- why a particular guard, step block, or step is relevant to the current outcome;
- which playbook-run profile is active;
- whether that profile came from explicit caller choice or playbook defaults;
- which overrides are active;
- which next action a human or agent can take when that can be inferred safely.

`explain` is a reasoning surface, not merely a verbose restatement of `check` or `plan`.

## Why this matters

For agent-authored workflows, `execute` alone is not enough.

The runtime needs modes that:
- reduce risk;
- improve reviewability;
- provide machine-readable reasoning;
- support both coarse-grained and specific questions from humans and agents.

## Runtime ownership of mode semantics

The runtime owns `check`, `plan`, `execute`, `explain`, and future next-safe-action semantics.
Connector operations should not each reimplement those modes locally.

Runtime may derive these modes from a shared internal decision model.
The modes are distinct query intents over runtime decision state, not necessarily fully separate computation paths.

Instead, runtime should derive higher-level execution meaning from structured operation contracts and structured operation outcomes.

Implications:
- connector operations may provide local observations, effect summaries, diagnostics, and supplementary raw detail;
- runtime combines those local results with workflow block structure, guard evaluation, profiles, and policy to determine blocked state, plan shape, explanation, and next safe action;
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
