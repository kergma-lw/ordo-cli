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

## Permanent exclusions

- Local expressions must never perform effectful connector work by themselves.
- Local expressions must never smuggle hidden workflow control structures such as looping or open-ended branching.
- Local expressions must never rely on project-defined syntax whose meaning is outside the stable product contract.
- Local expressions must never become a user-extensible language with workflow-defined functions, macros, or operators.

## Product discipline

- The product should prefer one local-expression family with context-specific restrictions over multiple independent expression languages for nearby workflow surfaces.
- Syntax and evaluation detail may differ by authored context, but those differences must not silently fragment the conceptual model into unrelated expression systems.
