# Invariants

## Core invariants

- unknown fields fail validation
- unknown operations fail resolution
- workflow holds orchestration, not algorithmic implementation
- structured result is required
- `check`, `plan`, `execute`, and `explain` are baseline runtime modes
- blocked-before-execution is distinct from execution failure
- runtime explanation is a structured surface, not merely logs or tracebacks
- runtime remains analysis-first rather than execute-first
- runtime is usable as a machine-readable decision surface, not only as an execution entrypoint
- contract-level runtime structures are losslessly JSON-serializable
- runtime decision surfaces remain machine-readable without format-specific parsing beyond standard JSON data handling

## Drift rule

If a change breaks any invariant, `meta/` must be updated explicitly in the same work.
