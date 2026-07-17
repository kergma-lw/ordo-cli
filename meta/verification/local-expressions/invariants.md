# Local expression invariants

## Context discipline

- Local expressions remain one product-owned expression family rather than drifting into unrelated per-context languages.
- Condition-oriented and value-oriented contexts remain explicitly distinguished.
- Each expression-bearing context has explicit documented root restrictions.
- Surface-syntax differences do not silently redefine dependency rules.

## Root discipline

- `inputs...`, `args...`, `state...`, and `step...` keep distinct documented meanings.
- `step...` remains execution-local and must not drift into contexts that are meant to stay pre-execution.
- Include bindings preserve caller scope without turning fragment bodies into implicit owners of caller-local step data.

## Guard-context discipline

- Guard context must not depend on `step...`.
- Guard context must remain compatible with read-only, pre-execution analysis.
- Guard conditions must remain explainable as workflow-visible policy rather than hidden connector-local verdicts.

## Value-context discipline

- Embedded value contexts must not drift into effectful connector execution.
- Value-oriented local expressions must not grow hidden workflow-control semantics.

## Drift checks

- Documentation must not reintroduce separate first-class expression species such as an unrelated guard language versus an unrelated value language.
- Context-specific docs must stay aligned with the domain definition in `domain/local-expressions.md`.
