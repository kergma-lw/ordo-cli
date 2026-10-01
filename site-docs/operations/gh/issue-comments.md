# GitHub issue comments

the workflow's GitHub repository context already names the normal repository target and workflow logic now needs prior discussion for one issue there.

Probe the comment thread of one GitHub issue as a typed list of recent comments plus total count metadata. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- Workflow logic needs to inspect prior discussion, count comments, or publish a compact conversation summary before taking another step.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.
- `limit`: optional.

## Result and boundary

- Usable result fact: `issue_ref`.
- Usable result fact: `total_count`.
- Usable result fact: `comments`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Reading the issue's main body, labels, or state; use connector.gh.issue for the broader issue snapshot.
- Posting a new comment; use connector.gh.issue.comment.add for that effectful change.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.issue`](issue.md): Sibling probe for the issue snapshot rather than its comment list
- [`connector.gh.issue.comment.add`](issue-comment-add.md): Action for appending one new comment to the same thread
- [`connector.gh.issue.body.append`](issue-body-append.md): Issue-body mutation surface when the update belongs in the issue body rather than the comment thread

## Inspect next

- connector.gh.issue
- connector.gh.issue.comment.add
- connector.gh.issue.body.append

## Exact machine contract

Use `ordo-help operation gh.issue.comments --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_issue_comments_step

Inspect the issue comment thread with one explicit limit and register the resulting comment snapshot.

```yaml
  - name: list-comments
    uses: gh.issue.comments
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      limit: 20
    register: comments_snapshot
```
