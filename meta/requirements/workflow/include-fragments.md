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
- Registered step results must not cross included-fragment boundaries in the MVP.
- A reusable fragment should not depend on hidden external `step...` names declared outside that fragment.
- Direct fragment-body references to caller-local `step...` names must remain invalid in the MVP.
- Explicit caller-local `step...` bindings passed through include `with` are valid because the dependency stays visible at the include site rather than hidden inside the fragment body.
