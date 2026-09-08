# GitHub repository input identity

## Scope and grammar

The shared repository identity contract applies to fields named
`repository` in GitHub operation inputs and `connector_contexts.gh.repository`.
Normalization, splitting, bootstrap, and review must use the same grammar:

- Accept strings only and trim with `strip(' ')`, removing ASCII spaces only.
- Full-match ASCII `[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+`.
- Reject either part equal to `.` or `..`, and reject owners starting with `-`.
- Repository names `.github`, `-demo`, and `-` remain syntactically route-safe.
- Preserve case; do not impose length, account-registry, or existence validation.
- Reject controls, non-ASCII whitespace, `?`, `#`, `%`, backslashes, and URLs.
  This is a literal operand grammar, not decoding or encoding arbitrary URLs.

## Validation and targeting

Invalid context must fail before authentication. Explicit operation input must
be validated before repository API requests, but may follow the existing auth
bootstrap. Preserve existing failure codes with a clear format diagnostic.

Connector context is a default target, not an authorization allowlist. A valid
explicit other repository remains allowed with an override warning. Review
uses the same normalized identity when comparing an explicit target to context.

## Separate contracts

API-response `nameWithOwner` values and composite `content_refs` parsing have
separate, unchanged trust contracts. This input rule must not be advertised as
validation of all arbitrary API-response values, or as evidence of demonstrated
SSRF or authentication bypass.
