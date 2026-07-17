# Gap: hard-removal preparation for deprecated local-expression surfaces

## Status

Prepared, but intentionally not executed.

The project is still in the warning window defined by `adr/0006-local-expressions-deprecation-plan.md`.

## Deprecated surfaces covered here

- embedded step conditions written as `if: ${...}`;
- object-form guard entries written as `- uses: namespace.name`.

## Current inventory

### Embedded `if: ${...}`

After the latest cleanup wave, embedded `if: ${...}` no longer remains in the tracked workflow, include, or example materials that are meant to model the preferred authored surface.

The compatibility form may still survive in:

- warning-oriented tests;
- migration notes or historical discussion documents;
- any future intentionally compatibility-oriented examples.

### Object-form guard `uses:` entries

After the latest cleanup wave, object-form guard `uses:` entries no longer remain in the tracked workflow materials that are meant to model the preferred authored surface.

They still appear in compatibility-oriented reference discussion such as:

- `meta/data/workflow/shape.md`
- `docs/format.md`

They may also remain in warning-oriented tests or historical notes.

## Execution checklist for future hard removal

This checklist is intentionally dormant until the warning window is declared complete.

### Gate 0: policy readiness

- [ ] Explicitly end the current v0 warning window in a new contract or ADR change.
- [ ] Decide the target release or contract revision for hard removal.
- [ ] Decide whether any temporary migration tooling or one-shot codemod is required.

### Gate 1: authored material readiness

- [x] Rewrite preferred workflow, include, and example materials away from embedded `if: ${...}`.
- [x] Rewrite preferred workflow materials away from object-form guard `uses:` entries.
- [ ] Re-audit the repository for any newly introduced deprecated authored forms before removal lands.

### Gate 2: parser and validation changes

### For embedded `if: ${...}`

- [ ] Remove the embedded-compatibility parsing branch for step-condition contexts.
- [ ] Remove the deprecation warning path and replace it with a hard validation error.
- [ ] Update workflow contract metadata, help output, and examples so only bare `if` remains documented.
- [ ] Refresh tests that currently assert warning behavior for embedded `if: ${...}`.

### For object-form guard `uses:` entries

- [ ] Remove the compatibility-only warning path for object-form guard entries.
- [ ] Replace compatibility acceptance with a hard validation error.
- [ ] Update workflow contract and format documentation so guard object form no longer appears as a valid authored surface.
- [ ] Refresh tests that currently assert warning behavior for object-form guards.

## Why this stays a prep note

The project has not yet declared the warning window complete.

This note exists so that a later hard-removal decision can be executed deliberately, with a concrete checklist and without rediscovering the migration surface from scratch.
