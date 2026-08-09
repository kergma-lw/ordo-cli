# Local expression requirements

## Role

- Local expressions are a workflow-owned declarative surface for deriving local values and conditions.
- They must not become a second orchestration language, a connector-execution surface, or a hidden scripting layer.
- Local expressions may appear in multiple contexts while remaining one product-owned expression family.

## Common obligations

- Every expression-bearing context must define which local roots are allowed there.
- Every expression-bearing context must define whether the expression is value-producing or condition-producing.
- Every expression-bearing context must preserve reviewability and explainability.
- Validation and diagnostics must identify invalid references or unsupported context use before effectful execution begins whenever the surrounding context permits that analysis.

## Context families

- The contract must distinguish condition-oriented contexts from value-oriented contexts.
- A condition-oriented context must not silently inherit the dependency rules of a value-oriented context, or vice versa.

## Common local roots

- `inputs...` is the common workflow input surface.
- `args...` is the fragment-local argument surface.
- `state...` is the runtime-state read surface when the context explicitly allows state reads.
- `step...` is the execution-local registered-step-result surface when the context explicitly allows step-result reads.

## Non-effectful observation dependencies

- Local expressions may depend on product-defined non-effectful connector observations such as read-only probes.
- Such observation dependencies must remain reviewable, explicit, and compatible with the surrounding context policy.
- A context may allow non-effectful probe observation without thereby allowing effectful connector execution.

## Derived values and representation adapters

- Local expressions may derive intermediate values from already available values.
- A workflow may declare workflow-local named expression bindings through a top-level `let` mapping.
- A `let` binding must denote one immutable local expression rather than a mutable variable, macro expansion, or user-defined function.
- A `let` binding must remain workflow-local and must not participate in inheritance, export, or cross-workflow resolution.
- A `let` binding must not reference another `let` binding.
- `let` bindings must not relax context gating; a binding is valid only in authored contexts where the equivalent inline expression would also be valid.
- Product-defined representation adapters may interpret values through stable representations such as markdown, html, json, yaml, and string.
- Representation-adapter operations must remain pure, local, and value-producing.
- Representation-adapter operations may return further derived values or addressable focus values for additional pure local evaluation.
- A context may allow read-only representation-adapter projections while still forbidding adapter write paths such as `->...`.
- Representation adapters require one shared product-defined invocation seam so concrete adapter families can participate in local-expression evaluation consistently.
- The authored addressing or selection surface between an adapter name and a terminal mutation may be adapter-defined.
- The product must not require all adapters to share one identical middle syntax when their represented structures differ materially.
- Adapter-specific authored syntax should be documented in adapter-specific requirements rather than overloaded into the shared core requirements.
- Any terminal representation-adapter mutation must return the updated root value of the adapted representation.
- Any update-style representation-adapter operation must return a new derived value rather than persisting change by itself.

## Canonical core boundary

- The canonical local-expression core should include shared non-effectful constructs for observation, comparison, composition, and value derivation.
- Shared non-effectful constructs may include literals, lists, local-root references, read-only probe observations, boolean operators, comparison operators, pipelines, built-ins, representation-adapter operations, and bounded collection-shaping filters.
- Effectful connector operations must remain outside the canonical local-expression core even when they are part of the wider connector surface.

## Product-defined pipeline filter surface

- Pipeline filters are product-defined local-expression operations applied to one already evaluated input value through the `value | filter(...)` surface.
- A pipeline filter must not widen context policy, introduce effectful connector work, or become a workflow-defined extension point.
- The product-defined pipeline filter set must be documented explicitly rather than inferred only from implementation code.
- The current product-defined filter set is:
  - `lower`;
  - `trim`;
  - `slug`;
  - `eq(...)`;
  - `ne(...)`;
  - `not`;
  - `is_string`;
  - `is_number`;
  - `is_integer`;
  - `is_boolean`;
  - `in(container)`;
  - `field(path)`;
  - `lookup(key)`;
  - `only(field=value)` / `only(field!=value)`;
  - `flatten`;
  - `first`;
  - `last`;
  - `length`;
  - `unique`.
- `lower`, `trim`, and `slug` are string-to-string transforming filters.
- `eq(...)`, `ne(...)`, `not`, `is_string`, `is_number`, `is_integer`, `is_boolean`, and `in(container)` are boolean-producing filters.
- `field(path)`, `lookup(key)`, `only(field=value)` / `only(field!=value)`, `flatten`, `first`, `last`, `length`, and `unique` are pure value-shaping filters over already evaluated JSON-shaped values.
- Predicate-style filters such as `is_string`, `is_number`, `is_integer`, and `is_boolean` must accept any already evaluated local-expression value and return `true` or `false` without implicit coercion.
- `eq(...)` and `ne(...)` compare without implicit coercion.
- `in(container)` must evaluate its argument as a container expression and must require that container to produce a list value.
- `in(container)` must compare the pipeline input against list members without implicit coercion.
- `in(container)` must fail when the container expression does not produce a list rather than silently reinterpreting strings, objects, or scalars as membership containers.
- `field(path)` must support object input and array input.
- `field(path)` on an object must return the addressed field value and must fail when the addressed path is missing.
- `field(path)` on an array must return an array of per-item addressed values.
- `field(path)` on an array must yield `null` for an item whose addressed path is missing rather than failing the whole filter.
- `field(path)` must fail on scalar or `null` input rather than silently coercing it into an object or singleton list.
- `field(path)` path syntax must support at least dotted field access and zero-based list indexing, for example `results` and `results[0]`.
- `lookup(key)` must support object input only.
- `lookup(key)` must require its argument to evaluate to a string key.
- `lookup(key)` on an object must return the exact value stored under that key.
- `lookup(key)` on an object must fail when the addressed key is missing.
- `lookup(key)` must fail on array, scalar, or `null` input rather than reinterpreting those shapes as object-like containers.
- `only(field=value)` and `only(field!=value)` must require array input.
- `only(...)` must keep only array elements whose addressed field path exists and satisfies the authored comparison.
- `only(...)` must treat a missing addressed field path on one item as a non-match rather than as a whole-filter failure.
- `only(...)` must fail on non-array input.
- `flatten` must require array input and must flatten exactly one list nesting level.
- `flatten` must fail on non-array input.
- `first` and `last` must require array input.
- `first` and `last` must return `null` on an empty array rather than failing.
- `first` and `last` must fail on non-array input.
- `length` must accept array, object, and string input.
- `length` over an array returns item count, over an object returns key count, and over a string returns character count.
- `length` must fail on other input shapes rather than silently coercing them.
- `unique` must require array input and must fail on non-array input.
- `unique` must preserve encounter order and keep the first occurrence of each value.
- `unique` equality must follow normalized JSON value equality without implicit coercion.
- `unique` must ignore object key order when comparing objects.
- `unique` must treat array element order as significant when comparing arrays.
- `unique` must treat numerically distinct forms such as `1` and `1.0` as different values.

## Probe-call execution model

- The canonical local-expression execution model must define how read-only probe-call nodes are evaluated without treating them as a second parser or second expression family.
- The canonical engine must remain the owner of probe-call node semantics, context gating, dependency visibility, caching expectations, trace shape, and diagnostics.
- Any external read-only observation needed to satisfy a probe call must pass through an explicit engine-facing probe-observation interface rather than through ad hoc legacy helper paths.
- Repeated equivalent read-only observation requests within one evaluation scope must reuse one observed result.
- A failed read-only observation must fail the surrounding expression evaluation rather than silently degrading it.
- A context that forbids non-effectful external observation must reject probe-call nodes through normal context-policy enforcement.

## Permanent exclusions

- Local expressions must never perform effectful connector work by themselves.
- Local expressions must never smuggle hidden workflow control structures such as looping or open-ended branching.
- Local expressions must never rely on project-defined syntax whose meaning is outside the stable product contract.
- Local expressions must never become a user-extensible language with workflow-defined functions, macros, or operators.
- Workflow-local `let` bindings must never become a second workflow-defined abstraction layer with parameters, overrides, or dependency chaining.
- Representation-adapter operations must never perform connector invocation, hidden I/O, or other effectful work.
- Representation-adapter families and operations must remain product-defined rather than workflow-defined extensions.

## Product discipline

- The product should prefer one local-expression family with context-specific restrictions over multiple independent expression languages for nearby workflow surfaces.
- Context-specific restrictions should change allowed dependencies or expected result shape rather than introducing separate read-only execution engines for equivalent expression constructs.
- Syntax and evaluation detail may differ by authored context, but those differences must not silently fragment the conceptual model into unrelated expression systems.
- Condition-oriented contexts such as guards may still impose a result-shape contract, for example requiring a final boolean result without thereby becoming a separate expression language.
