# GitHub pr reviews

the workflow's GitHub repository context already names the normal repository target and the workflow needs submitted review records there by pull number.

Probe submitted GitHub pull-request reviews as typed review records with verdict, author, timestamp, and optional reviewed commit id. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The workflow needs reviewer decisions such as APPROVED or CHANGES_REQUESTED without reconstructing them from comments or timeline events.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `pull_number`: required.
- `limit`: optional.

## Result and boundary

- Usable result fact: `pull_ref`.
- Usable result fact: `total_count`.
- Usable result fact: `reviews`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Free-form top-level discussion; use connector.gh.pr.comments when the workflow needs ordinary PR conversation.
- Per-line feedback details; use connector.gh.pr.review_comments for code-anchored remarks.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.pr`](pr.md): Parent PR snapshot that carries only aggregate review decision, not the individual submitted reviews
- [`connector.gh.pr.review_comments`](pr-review-comments.md): Sibling probe for detailed line-level review discussion
- [`connector.gh.pr.timeline`](pr-timeline.md): Sibling probe for lifecycle events that may surround review activity

## Inspect next

- connector.gh.pr.review_comments
- connector.gh.pr.timeline
- connector.gh.pr

## Exact machine contract

Use `ordo-help operation gh.pr.reviews --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_reviews_step

Inspect submitted pull-request reviews with one explicit limit before interpreting approval or change-request history.

```yaml
  - name: Load pull request reviews
    uses: gh.pr.reviews
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_reviews
```
