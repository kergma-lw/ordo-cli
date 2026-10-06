# GitHub issue close

the workflow's GitHub repository context already names the normal repository target and the workflow now needs to close one issue there by issue number.

Close one existing GitHub issue by repository and issue number. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.

## Use when

- A workflow has already decided that the issue should be closed and needs one typed action result instead of a shell-level command.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.

## Result and boundary

- Usable result fact: `issue_ref`.
- Usable result fact: `state`.
- Usable result fact: `closed`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails.

## Do not use for

- Explaining the closure in conversation text; add a comment first when the workflow should leave a human-facing note.
- Closing a pull request; use the pull-request connector family for PR-specific lifecycle actions.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.issue`](issue.md): Probe the issue first when closure depends on current issue state or metadata
- [`connector.gh.issue.comment.add`](issue-comment-add.md): Leave one final note on the issue before or instead of closing it
- [`connector.gh.issue.body.append`](issue-body-append.md): Append a closing note to the body when the workflow needs body mutation rather than state transition

## Inspect next

- connector.gh.issue
- connector.gh.issue.comment.add
- connector.gh.issue.body.append

## Exact machine contract

Use `ordo-help operation gh.issue.close --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_issue_close_step

Close one existing GitHub issue after earlier workflow steps have already selected the target issue number.

```yaml
  - name: Close issue
    uses: gh.issue.close
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
```
