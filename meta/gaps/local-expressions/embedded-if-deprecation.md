# Gap: deprecation path for embedded step `if: ${...}`

## Status

Resolved by `adr/0006-local-expressions-deprecation-plan.md`.

The preferred step-condition surface is now bare `if`, while embedded
`if: ${...}` remains supported only for compatibility.

## Problem

The runtime and docs can already distinguish:

- preferred native step conditions such as `if: step.issue.outputs.open`;
- deprecated embedded compatibility forms such as `if: ${step.issue.outputs.open}`.

The product-level deprecation path is now fixed:

- runtime emits explicit validation warnings for embedded `if: ${...}`;
- the compatibility form remains accepted during the current v0 warning window;
- help and introspection rely on contract metadata and docs rather than a separate dedicated warning screen;
- removal, if it happens later, requires an explicit workflow-contract revision after the warning window.

## Why this matters

Without an explicit deprecation path, the product risks drifting into a long-lived
double surface where both forms are valid but the preferred contract is not enforced.

That weakens:

- authoring consistency;
- machine-teachable surface guidance;
- future cleanup of legacy condition embedding.

## Result

This note remains only as a historical record of the gap that existed before ADR 0006 fixed the retirement plan.
