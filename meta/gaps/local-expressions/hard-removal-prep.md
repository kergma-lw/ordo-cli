# Gap: hard-removal preparation for deprecated local-expression surfaces

## Status

Prepared, but intentionally not executed.

The project is still in the warning window defined by `adr/0006-local-expressions-deprecation-plan.md`.

## Deprecated surfaces covered here

- embedded step conditions written as `if: ${...}`;
- object-form guard entries written as `- uses: namespace.name`.

## Current inventory

### Embedded `if: ${...}`

Observed in non-source workflow and example material at least in:

- `.ordo/workflows/open-task.yml`
- `examples/preflight-halt.yaml`
- `includes/github/ensure-task-in-project.yml`
- `includes/github/comment-and-set-status.yml`
- `includes/github/prepare-task-branch.yml`
- `includes/git/run-and-commit-generated-changes.yml`
- `includes/git/merge-task-branch-into-main.yml`
- `docs/format.md`

These occurrences show that the compatibility form is still actively demonstrated or reused in workflow material.

### Object-form guard `uses:` entries

Observed in authored workflow material at least in:

- `.ordo/workflows/open-task.yml`
- `.ordo/workflows/close-task.yml`

Also described in reference documentation such as:

- `meta/data/workflow/shape.md`
- `docs/format.md`

## What future hard removal would require

### For embedded `if: ${...}`

1. Rewrite all workflow, include, example, and documentation occurrences to bare condition form.
2. Remove the embedded-compatibility parsing branch for step-condition contexts.
3. Remove the deprecation warning path and replace it with a hard validation error.
4. Update workflow contract metadata, help output, and examples so only bare `if` remains documented.
5. Refresh tests that currently assert warning behavior for embedded `if: ${...}`.

### For object-form guard `uses:` entries

1. Rewrite remaining authored workflows and docs to native guard expressions.
2. Remove the compatibility-only warning path for object-form guard entries.
3. Replace compatibility acceptance with a hard validation error.
4. Update workflow contract and format documentation so guard object form no longer appears as a valid authored surface.
5. Refresh tests that currently assert warning behavior for object-form guards.

## Why this stays a prep note

The project has not yet declared the warning window complete.

This note exists so that a later hard-removal decision can be executed deliberately, with a concrete checklist and without rediscovering the migration surface from scratch.
