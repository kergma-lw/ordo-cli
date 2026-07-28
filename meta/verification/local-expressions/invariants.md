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
- Guard context may allow pure built-ins and read-only representation-adapter projections without regressing into a separate guard-only language.
- Guard context must continue to forbid representation-adapter write paths such as `->...`.
- Guard evaluation must end in a boolean result; non-boolean success must remain an error rather than collapsing into implicit truthiness.

## Value-context discipline

- Embedded value contexts must not drift into effectful connector execution.
- Value-oriented local expressions must not grow hidden workflow-control semantics.

## Pipeline-filter discipline

- Pipeline filters remain an explicit product-defined contract rather than an implementation-only registry.
- Product-defined pipeline filters must not drift into workflow-defined extensibility.
- Predicate filters such as `is_string`, `is_number`, `is_integer`, and `is_boolean` must remain boolean-only and must not silently introduce coercion semantics.
- Membership filters such as `in(container)` must preserve explicit list-container discipline rather than silently treating arbitrary strings, objects, or scalars as containers.
- Boolean-producing filters must keep stable boolean result shape across contexts.
- Collection-shaping filters must remain bounded data-shaping helpers over already available JSON-shaped values rather than drifting into a nested collection-programming sublanguage.
- Collection-shaping filters must fail on unsupported input shapes unless the documented contract explicitly defines a different outcome for that filter and shape.
- `field(path)` must preserve the hybrid missing-path rule: object input with a missing path fails, while array input yields `null` for an item with a missing path.
- `flatten` must remain single-level rather than silently becoming recursive.
- `first` and `last` must keep the documented empty-array outcome of `null`.
- `unique` must remain stable, must keep first occurrence, and must preserve strict normalized JSON equality including the distinction between `1` and `1.0`.

## Workflow-local binding discipline

- Workflow-level `let` remains one local-expression naming surface rather than a second expression language.
- A `let` binding does not relax the context restrictions that would apply to the equivalent inline expression.
- A `let` binding may not reference another `let` binding.
- Reserved roots must not drift into ordinary reusable binding names.

## Representation-adapter discipline

- Representation-adapter docs must preserve the boundary between host-owned outer binding evaluation and adapter-family body evaluation.
- Representation-adapter docs must not drift back toward bare host-root references inside adapter-owned body syntax.
- Adapter-related failures should remain attributable either to outer binding resolution or to adapter-family evaluation rather than collapsing those phases into one opaque error class.

## Drift checks

- Documentation must not reintroduce separate first-class expression species such as an unrelated guard language versus an unrelated value language.
- Context-specific docs must stay aligned with the domain definition in `domain/local-expressions.md`.
