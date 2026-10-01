# GitHub pr review-comments

the workflow's GitHub repository context already names the normal repository target and the workflow needs file-anchored PR review comments there by pull number.

Probe line-level review comments on one GitHub pull request as typed code-anchored discussion records with path and line metadata. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The workflow needs reviewer feedback tied to concrete files or lines rather than only top-level PR conversation.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `pull_number`: required.
- `limit`: optional.

## Result and boundary

- Usable result fact: `pull_ref`.
- Usable result fact: `total_count`.
- Usable result fact: `comments`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Top-level conversation comments on the PR body; use connector.gh.pr.comments for that broader discussion thread.
- Submitted review verdicts without line detail; use connector.gh.pr.reviews for the review-level decisions.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.pr.diff`](pr-diff.md): Sibling probe for changed-file context that these line comments often reference
- [`connector.gh.pr.comments`](pr-comments.md): Sibling probe for top-level conversation comments rather than file-anchored review remarks
- [`connector.gh.pr.reviews`](pr-reviews.md): Sibling probe for submitted review verdicts rather than individual line comments

## Inspect next

- connector.gh.pr.diff
- connector.gh.pr.reviews
- connector.gh.pr.comments

## Exact machine contract

Use `ordo-help operation gh.pr.review_comments --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_review_comments_step

Inspect line-level review comments with one explicit limit when the workflow needs file-anchored reviewer feedback.

```yaml
  - name: load-pr-review-comments
    uses: gh.pr.review_comments
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_review_comments
```
