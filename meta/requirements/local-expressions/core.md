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
- Product-defined representation adapters may interpret values through stable representations such as markdown, html, json, and string.
- Representation-adapter operations must remain pure, local, and value-producing.
- Representation-adapter operations may return further derived values or addressable focus values for additional pure local evaluation.
- The authored addressing or selection surface between an adapter name and a terminal mutation may be adapter-defined.
- The product must not require all adapters to share one identical middle syntax when their represented structures differ materially.
- Any terminal representation-adapter mutation must return the updated root value of the adapted representation.
- Any update-style representation-adapter operation must return a new derived value rather than persisting change by itself.

## Canonical core boundary

- The canonical local-expression core should include shared non-effectful constructs for observation, comparison, composition, and value derivation.
- Shared non-effectful constructs may include literals, lists, local-root references, read-only probe observations, boolean operators, comparison operators, pipelines, built-ins, and representation-adapter operations.
- Effectful connector operations must remain outside the canonical local-expression core even when they are part of the wider connector surface.

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
- Representation-adapter operations must never perform connector invocation, hidden I/O, or other effectful work.
- Representation-adapter families and operations must remain product-defined rather than workflow-defined extensions.

## Product discipline

- The product should prefer one local-expression family with context-specific restrictions over multiple independent expression languages for nearby workflow surfaces.
- Context-specific restrictions should change allowed dependencies or expected result shape rather than introducing separate read-only execution engines for equivalent expression constructs.
- Syntax and evaluation detail may differ by authored context, but those differences must not silently fragment the conceptual model into unrelated expression systems.
