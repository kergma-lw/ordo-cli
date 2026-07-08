# Workflow requirements for fragment runs

## Status

- `run` is a planned workflow surface and is not yet part of the current stable workflow shape.

## Role

- Workflow authoring should be able to invoke reusable workflow fragments through a runtime-scoped `run` surface when static `include` semantics are insufficient.
- `run` should carry the invocation semantics that would otherwise make `include` stop being a clean static-composition primitive.

## Authoring surface

- A future workflow block item may invoke one reusable fragment through `run`.
- A future `run` item should support `with` for explicit fragment-argument binding.
- A future `run` item should support caller-scoped eligibility modifiers such as `if`.
- `run` should reuse the existing fragment `args` contract rather than inventing a second argument language.

## Scope and data flow

- `run` argument bindings should be interpreted in caller scope.
- Caller-scoped `run` argument bindings may read prior registered caller `step...` results.
- Fragment-local `args...` should expose only the bound invocation arguments, not unrestricted caller-local runtime scope.
- Direct fragment-body references to caller-local `step...` names should remain invalid unless a later explicit export surface is introduced.

## Explainability

- `plan` and `explain` should be able to preserve that one reusable fragment was invoked as a distinct runtime node rather than only as static expansion residue.
- Runtime-facing outputs should preserve enough information to distinguish caller-side invocation gating from callee-side fragment execution.

## Coexistence with `include`

- `include` should remain valid for static composition even after `run` is introduced.
- Introducing `run` should be preferred over silently widening `include` when the needed semantics are invocation-scoped rather than composition-scoped.
