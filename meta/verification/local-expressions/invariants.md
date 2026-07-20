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

## Representation-adapter discipline

- Representation-adapter docs must preserve the boundary between host-owned outer binding evaluation and adapter-family body evaluation.
- Representation-adapter docs must not drift back toward bare host-root references inside adapter-owned body syntax.
- Adapter-related failures should remain attributable either to outer binding resolution or to adapter-family evaluation rather than collapsing those phases into one opaque error class.

## Drift checks

- Documentation must not reintroduce separate first-class expression species such as an unrelated guard language versus an unrelated value language.
- Context-specific docs must stay aligned with the domain definition in `domain/local-expressions.md`.
