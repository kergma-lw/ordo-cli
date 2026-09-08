# GH issue identity contract

## Summary

Issue-oriented `gh` operations should use structured issue identity inputs:

- `repository` — GitHub repository in `OWNER/REPO` form
- `issue_number` — positive integer issue number

The older single-string `issue_ref` form is no longer part of the input contract.

## Scope

This input shape applies to issue-oriented operations such as:

- `gh.issue`
- `gh.issue.close`
- `gh.issue.body.replace`
- `gh.issue.body.append`
- `gh.issue.comment.add`
- `gh.project.issue`
- `gh.project.issue.add`
- `gh.project.issue.field_single_select.set`
- `gh.project.issue.field_iteration.set`
- `gh.project.issue.field_single_select.set`
- `gh.project.issue.field_single_select.set`
- `gh.project.issue.field_single_select.set`
- `gh.project.issue.field_number.set`

## Validation

- `repository` and `connector_contexts.gh.repository` use literal ASCII `OWNER/REPO`, not URLs. Trim ASCII spaces only (`strip(' ')`), then full-match `[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+`. Reject either part `.` or `..`, and owners starting with `-`. Repository names `.github`, `-demo`, and `-` remain syntactically route-safe.
- Preserve case without length, account-registry, or existence validation. Controls, non-ASCII whitespace, `?`, `#`, `%`, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs.
- Invalid context fails before authentication. Explicit input validation precedes repository API requests but may follow the existing authentication bootstrap. Existing failure codes remain with clear format diagnostics.
- Context is a default, not an authorization allowlist. Valid explicit other repositories remain allowed with an override warning; normalization, splitting, bootstrap, and review share the pure-model grammar.
- `issue_number` must be a positive integer
- diagnostics should distinguish invalid repository input from invalid issue number input

## Compatibility

- public operation contracts should publish `repository` and `issue_number` as the primary inputs
- built-in workflows, examples, and help surfaces should prefer the structured input form

## Outputs

API-response `nameWithOwner` and composite `content_refs` parsing retain separate,
unchanged trust contracts. Input validation does not establish that arbitrary API
responses are validated, or demonstrate SSRF or authentication bypass. See the
[normative repository input contract](../meta/requirements/connector/gh-repository-identity.md).

- existing output fields remain stable during the migration
- operations that already expose `issue_ref` may keep it as a convenience field
- this migration does not require every output shape to be normalized before the input split lands
