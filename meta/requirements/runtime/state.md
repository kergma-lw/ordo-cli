# Runtime requirements for state

## Role

- The runtime may expose a small built-in persistent state capability for workflow coordination across runs.
- This capability belongs to runtime rather than to the public connector surface.
- The initial purpose is to remember small pieces of workflow-owned state such as task-to-branch linkage.

## MVP scope

- The initial authoring surface should support a top-level `states` mapping that names runtime-managed state locations.
- The initial authoring surface should support explicit effectful mutation through `state_set` and `state_delete` step forms.
- The initial authoring surface should support direct value reads through `states...` references rather than requiring a dedicated `state_get` step.
- The initial capability should remain intentionally small and should not require a general-purpose memory or fact system.

## Minimal semantics

- A named state entry should identify a runtime-managed persistent location.
- `state_set` should create or replace the addressed value deterministically.
- `state_delete` should remove the addressed value deterministically.
- State reads should resolve to stored values through the same stable state path surface used by authoring.
- Missing state reads should remain structured and predictable rather than falling back to hidden defaults.

## Boundary discipline

- Runtime state should not be modeled as a connector family.
- Runtime state should not be described as a broad fact or knowledge system at this stage.
- Runtime state should not introduce a broad query language, lock model, reconciliation model, or multi-scope memory model in the MVP.
- The MVP should prefer a narrow explicit surface over premature generalization.
