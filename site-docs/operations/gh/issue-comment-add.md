# GitHub issue comment add

the workflow's GitHub repository context already names the normal repository target and the workflow should leave one comment on one issue there.

Add one new comment to an existing GitHub issue and return the created comment id, URL, and body. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The workflow should leave a human-facing note in the issue conversation without rewriting the issue body.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.
- `body`: required.

## Result and boundary

- Usable result fact: `issue_ref`.
- Usable result fact: `comment_id`.
- Usable result fact: `url`.
- Usable result fact: `body`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails.

## Do not use for

- Updating the canonical issue description; use connector.gh.issue.body.append or connector.gh.issue.body.replace when the change belongs in the body itself.
- Reading prior comments; use connector.gh.issue.comments when the workflow needs observation rather than mutation.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.issue.comments`](issue-comments.md): Probe the existing comment thread before or after adding a new comment
- [`connector.gh.issue.body.append`](issue-body-append.md): Append durable text to the issue body instead of the comment thread
- [`connector.gh.issue.body.replace`](issue-body-replace.md): Rewrite the full issue body when the workflow owns the canonical description

## Inspect next

- connector.gh.issue.comments
- connector.gh.issue.body.append
- connector.gh.issue.close

## Exact machine contract

Use `ordo-help operation gh.issue.comment.add --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_issue_comment_add_step

Add one human-facing follow-up comment to the issue conversation without rewriting the issue body.

```yaml
  - name: Add closing comment
    uses: gh.issue.comment.add
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      body: inputs.close_comment
```
