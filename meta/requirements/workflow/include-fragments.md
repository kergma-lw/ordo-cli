# Workflow requirements for included fragments

## Role

- Workflow authoring should support reusable included fragments as a first-class composition surface.
- `include` should remain a static-composition primitive rather than silently absorbing runtime-scoped invocation semantics.
- Adding arguments to an included fragment should not by itself require `include` to become a runtime invocation surface.
- If reusable fragments later need caller-scoped runtime modifiers such as step-dependent conditions or loops, a separate invocation primitive such as `run` may coexist with `include` rather than overloading static composition.

## Authoring surface

- A workflow block item may include a fragment through `include`.
- An include item may optionally declare `with` to bind fragment arguments.
- `with` value expressions should be interpreted in caller scope before they become fragment-local `args...` bindings.
- Plain scalar strings in include-site `with` should be interpreted as caller-scoped expressions by default.
- Quoted strings in include-site `with` should remain explicit string literals.
- `include` should not be treated as a general runtime-scoped call node merely because fragment arguments are present.
- The included fragment file may declare human-facing metadata such as `description` and a fragment-local `args` contract.
- Fragment arguments should be referenced inside the included fragment as `args.<name>`.
- `with` keys should bind only declared fragment arguments.
- A fragment argument may be required, optional without a default, or optional with a declared default value.
- Declared fragment default values may include `null`.
- Omitting an optional fragment argument must remain distinct from binding that argument explicitly to `null`.

## Validation and diagnostics

- Include resolution must stay machine-checkable before execution.
- Validation must reject missing required fragment arguments.
- Validation must reject unknown argument bindings in `with`.
- Validation must reject malformed fragment argument declarations.
- Validation must accept omitted optional arguments when the fragment contract declares them as optional or supplies a default.
- Validation must preserve explicit `null` bindings rather than collapsing them into missing-argument behavior.
- Diagnostics should distinguish file-resolution failure from argument-binding failure.

## Boundary discipline

- Fragment-local arguments must not overwrite or masquerade as global workflow `inputs`.
- Persistent runtime state remains shared through `state...` across the assembled workflow.
- Included fragments should expand into the caller workflow execution order rather than introducing an implicit runtime invocation boundary.
- Registered step results declared inside an included fragment must remain available to later caller-visible steps exactly as earlier inline step registers remain available.
- Included fragment steps may read earlier caller-visible `step...` results wherever the surrounding local-expression context allows step-result access.
- Fragment-local `args...` remain fragment-local parameter bindings and must not be treated as a replacement for caller-visible execution-local `step...` scope.
- Duplicate register names across inline workflow steps and included fragment steps must fail validation rather than shadowing one another silently.
