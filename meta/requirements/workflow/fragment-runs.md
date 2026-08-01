# Workflow requirements for fragment runs

## Status

- `run` is a planned workflow surface and is not yet part of the current stable workflow shape.

## Role

- Workflow authoring should be able to invoke reusable workflow fragments through a runtime-scoped `run` surface when static `include` semantics are insufficient.
- `run` should carry the invocation semantics that would otherwise make `include` stop being a clean static-composition primitive.

## Authoring surface

- A future workflow step form may invoke one reusable fragment through `run`.
- A future `run` item should support `with` for explicit fragment-argument binding.
- A future `run` item should support caller-scoped eligibility modifiers such as `if`.
- `run` should reuse the existing fragment `args` contract rather than inventing a second argument language.
- Plain scalar strings in `run.with` and `run.for_each` should follow the same expression-first authored rule as other workflow value-bearing surfaces.
- Quoted strings in `run.with` and `run.for_each` should remain explicit string literals.
- The author-facing `run` surface should remain step-shaped so reusable fragment invocation still reads like one workflow action.
- If `run` later grows bounded `for_each`, that fan-out should stay part of the same `run` surface rather than introducing a second unrelated looping primitive.
- A bounded `for_each` fan-out on `run` may use either a named reusable fragment target or one inline short `steps` body as the repeated body.
- Inline `steps` repeated body should exist for short local cycles rather than forcing every small repeated body into a separately named fragment.
- Bounded `for_each` fan-out should not allow nested `guards` inside the repeated body.
- Nested `for_each` should remain invalid anywhere inside the repeated body, including inside inline repeated-body `steps`.

## Scope and data flow

- `run` argument bindings should be interpreted in caller scope.
- Caller-scoped `run` argument bindings may read prior registered caller `step...` results.
- Fragment-local `args...` should expose only the bound invocation arguments, not unrestricted caller-local runtime scope.
- Direct fragment-body references to caller-local `step...` names should remain invalid unless a later explicit export surface is introduced.
- If bounded `for_each` later uses inline `steps`, any step-level `register` declared inside that repeated body should remain local to one iteration and should be visible only to later steps in that same iteration body.

## Explainability

- `plan` and `explain` should be able to preserve that one reusable fragment was invoked as a distinct runtime node rather than only as static expansion residue.
- Runtime-facing outputs should preserve enough information to distinguish caller-side invocation gating from callee-side fragment execution.
- If bounded `for_each` is present, `plan`, `check`, and `explain` should preserve that one explicit fan-out node exists rather than flattening repeated invocations into an unstructured step list.

## Coexistence with `include`

- `include` should remain valid for static composition even after `run` is introduced.
- Introducing `run` should be preferred over silently widening `include` when the needed semantics are invocation-scoped rather than composition-scoped.
- If `run` later resolves more than one reusable target class, local workflow fragments should win on name collision so the nearest workflow-owned fragment body remains the default interpretation.
