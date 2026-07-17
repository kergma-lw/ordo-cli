# Gap: deprecation path for embedded step `if: ${...}`

## Status

This note records a real transition gap rather than a settled final policy.

The preferred step-condition surface is now bare `if`, while embedded
`if: ${...}` remains supported only for compatibility.

## Problem

The runtime and docs can already distinguish:

- preferred native step conditions such as `if: step.issue.outputs.open`;
- deprecated embedded compatibility forms such as `if: ${step.issue.outputs.open}`.

What is still open is the product-level deprecation path:

- whether runtime should emit explicit deprecation warnings;
- how long embedded `if: ${...}` should remain accepted;
- whether help and explain surfaces should flag the older form automatically;
- what migration ergonomics should exist for existing workflow files.

## Why this matters

Without an explicit deprecation path, the product risks drifting into a long-lived
double surface where both forms are valid but the preferred contract is not enforced.

That weakens:

- authoring consistency;
- machine-teachable surface guidance;
- future cleanup of legacy condition embedding.

## Desired outcome

The product should eventually define:

- whether embedded `if: ${...}` produces warnings during validation or help output;
- when, if ever, the compatibility form becomes hard-deprecated or removed;
- how migration should be communicated and automated.

This note does not decide the timeline. It only records that the compatibility
surface now exists and needs an explicit retirement policy later.
