# Runtime requirements for state

## Role

- The runtime may expose a small built-in persistent state capability for workflow coordination across runs.
- This capability belongs to runtime rather than to the public connector surface.
- The initial purpose is to remember small pieces of workflow-owned state such as task-to-branch linkage.

## MVP scope

- The initial authoring surface should support a playbook-level `states` mapping that names runtime-managed state locations.
- The initial authoring surface should support workflow-level logical state needs that remain separate from concrete project state declarations.
- The initial workflow `state_needs` surface should be marker-only rather than carrying richer per-need configuration fields.
- The initial authoring surface should support explicit effectful mutation through `state_set` and `state_delete` step forms.
- The initial authoring surface should support direct value reads through `state...` references rather than requiring a dedicated `state_get` step.
- The initial state access grammar should use one aligned path surface for reads, `state_set`, and `state_delete`.
- The initial capability should remain intentionally small and should not require a general-purpose memory or fact system.

## Minimal semantics

- A named state entry should identify a runtime-managed persistent location.
- Workflow state reads and writes should resolve through workflow logical state roles that are bound by the playbook to concrete state declarations.
- A workflow that declares a logical state need is not activatable without a corresponding playbook state binding.
- `state_set` should create or replace the addressed value deterministically.
- `state_delete` should remove the addressed value deterministically.
- State reads should resolve to stored values through the same stable state path surface used by authoring.
- Missing state reads should remain structured and predictable rather than falling back to hidden defaults.
- The initial stable state path should require a logical role, one `inputs...` key reference, and optional dotted field traversal.

## Boundary discipline

- Runtime state should not be modeled as a connector family.
- Runtime state should not be described as a broad fact or knowledge system at this stage.
- Runtime state should not introduce a broad query language, lock model, reconciliation model, or multi-scope memory model in the MVP.
- The MVP should prefer a narrow explicit surface over premature generalization.
- Runtime state should remain a cross-run memory surface rather than a substitute for per-run step registers.
- A workflow should not write or delete a logical state role before its final read of that same logical role.
- State mutation should remain a top-level workflow concern and should not appear inside included fragments or runtime-invoked fragments.
