# ADR 0006: deprecate legacy local-expression authored surfaces through warnings first

## Status

Accepted.

## Context

The local-expressions migration established two preferred authored surfaces:

- native guard expressions instead of object-form guard `uses:` entries;
- bare step `if` conditions instead of embedded `if: ${...}`.

The runtime already accepts the preferred forms and emits compatibility warnings for the legacy forms.

The remaining open question was the retirement policy for those deprecated surfaces.

## Decision

The project will keep both legacy forms valid during the current v0 warning window.

The deprecated forms are:

- object-form guard `uses:` entries;
- embedded step `if: ${...}`.

During this warning window:

- validation warnings remain the primary deprecation signal;
- contract metadata and docs may describe the forms as deprecated compatibility surface;
- help and introspection do not need a separate dedicated warning screen beyond that contract metadata.

Removal, if it happens, must wait until a later workflow-contract revision after at least one sustained warning period in the current v0 line.

## Consequences

- workflow authors keep a stable migration window rather than facing an immediate breaking change;
- validation warnings are the canonical runtime signal for these deprecated forms;
- docs and contract metadata should continue to mark the preferred versus compatibility surfaces clearly;
- a future hard deprecation can be introduced only as an explicit follow-up contract change rather than as an incidental parser cleanup.

## Follow-up preparation

The concrete inventory and checklist for any future hard removal is tracked in:

- `gaps/local-expressions/hard-removal-prep.md`
