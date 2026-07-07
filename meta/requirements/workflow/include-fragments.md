# Workflow requirements for included fragments

## Role

- Workflow authoring should support reusable included fragments as a first-class composition surface.
- The author-facing reuse surface should remain one `include` primitive whether or not arguments are bound.
- Adding arguments to an included fragment should not force authors to switch to a separate reuse verb.

## Authoring surface

- A workflow block item may include a fragment through `include`.
- An include item may optionally declare `with` to bind fragment arguments.
- The included fragment file may declare human-facing metadata such as `description` and a fragment-local `args` contract.
- Fragment arguments should be referenced inside the included fragment as `args.<name>`.
- `with` keys should bind only declared fragment arguments.

## Validation and diagnostics

- Include resolution must stay machine-checkable before execution.
- Validation must reject missing required fragment arguments.
- Validation must reject unknown argument bindings in `with`.
- Validation must reject malformed fragment argument declarations.
- Diagnostics should distinguish file-resolution failure from argument-binding failure.

## Boundary discipline

- Fragment-local arguments must not overwrite or masquerade as global workflow `inputs`.
- Persistent runtime state remains shared through `state...` across the assembled workflow.
- Registered step results must not cross included-fragment boundaries in the MVP.
- A reusable fragment should not depend on hidden external `step...` names declared outside that fragment.
