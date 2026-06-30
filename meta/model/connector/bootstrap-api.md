# Concrete executable bootstrap API proposal

## Role

This document defines the first concrete executable bootstrap API proposal for connector families.

Its purpose is to turn family bootstrap from metadata-only declaration into a real executable capability-check layer while keeping the pattern close to the existing publication-hook direction for operations.

## Bootstrap module shape

Each connector family bootstrap module should expose exactly two primary surfaces:

- `info()` — the uniform publication hook for the family bootstrap definition;
- `run(ctx)` — the bootstrap execution hook.

The publication hook is the family bootstrap publication point.
The execution hook is the family bootstrap execution point.

## Publication hook

The uniform publication hook should be:

```python
def info() -> PublishedBootstrap
```

`info()` should return the published bootstrap definition for the family.

The first executable bootstrap step should not require additional family-bootstrap globals beyond this publication hook.

## Published bootstrap definition

The minimal published bootstrap definition should expose at least:

- `prerequisites`
- `context_fields`
- `handler`

Implications:

- `prerequisites` describe shared family prerequisites rather than operation-local prerequisites;
- `context_fields` describe the family-level capability or context facts that bootstrap may provide on success;
- the published definition does not need operation-style `inputs`, `outputs`, `effects`, or `failure_modes` fields unless later code proves they are necessary.

## Execution hook

The bootstrap execution hook should be:

```python
def run(ctx: BootstrapContext) -> BootstrapOutcome
```

The hook should remain family-capability-oriented rather than operation-oriented.
It should not know which specific probe or action will later consume the bootstrap state.

## Bootstrap context

The minimal bootstrap context should expose at least:

- `command(argv, *, failures=...)` for command-backed capability checks;
- narrow environment access needed to discover shared family context;
- a way to report or accumulate shared capability facts when bootstrap succeeds.

The first executable bootstrap step should not require workflow-level policy state or operation-local inputs.

## Bootstrap outcome

The minimal bootstrap outcome should expose at least:

- `status`
- `summary`
- `diagnostics`
- `raw`
- `context`

Where:

- `status` reports bootstrap success or bootstrap failure at the family layer;
- `summary` gives a short human-readable family-level result;
- `diagnostics` carries structured bootstrap problems or warnings;
- `raw` carries supplementary command or transport detail when helpful;
- `context` carries shared family capability facts made available to later operation execution.

The bootstrap outcome is a connector-family capability result, not an operation result and not the full public runtime envelope.

## Command helper expectations

Bootstrap should be able to use the same low-level command helper pattern as operations where appropriate.

The minimum normalized failure keys for the first executable bootstrap step should be:

- `os_error`
- `nonzero`

Additional keys may be added later if executable bootstrap checks prove they are needed.

## Runtime expectations

Runtime should evaluate executable family bootstrap before operation-local logic when a family requires shared prerequisites.

Runtime should then:

- preserve bootstrap success or failure as its own layer;
- carry bootstrap `context` into later operation execution;
- keep bootstrap failures distinct from operation-local failures and workflow-policy outcomes.

## Git first-step expectations

For the Git family, the first executable bootstrap step should be able to detect at least:

- missing `git` binary;
- non-repository context.

On success, it may provide shared facts such as:

- repository root;
- repository availability confirmation.

Additional facts such as current branch should be included only if keeping them at bootstrap level remains semantically clean.

## Low-ceremony requirement

Bootstrap authoring should stay small and direct.

The first executable Git bootstrap should not require substantially more ceremony than a small probe module, except for the extra family-level context field in its outcome.

If executable bootstrap grows into a second large authoring framework, the boundary should be reconsidered before wider rollout.

## Open questions intentionally left to code work

The first bootstrap implementation step should answer these by code rather than by abstract generalization:

- whether bootstrap should share the exact command helper implementation with operation context or only the same pattern;
- whether bootstrap diagnostics need anything beyond the current local diagnostic shape;
- whether bootstrap `context` should remain an unstructured mapping at first or immediately grow a richer view type;
- whether runtime should cache bootstrap state per family per run or simply reevaluate it at the first straightforward integration point.
