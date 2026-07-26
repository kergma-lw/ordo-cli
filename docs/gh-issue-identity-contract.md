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

- `repository` must use `OWNER/REPO`
- `issue_number` must be a positive integer
- diagnostics should distinguish invalid repository input from invalid issue number input

## Compatibility

- public operation contracts should publish `repository` and `issue_number` as the primary inputs
- built-in workflows, examples, and help surfaces should prefer the structured input form

## Outputs

- existing output fields remain stable during the migration
- operations that already expose `issue_ref` may keep it as a convenience field
- this migration does not require every output shape to be normalized before the input split lands
