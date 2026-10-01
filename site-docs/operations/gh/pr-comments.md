# GitHub pr comments

the workflow's GitHub repository context already names the normal repository target and the workflow needs top-level PR discussion there by pull number.

Probe the regular conversation thread on one GitHub pull request as top-level discussion comments plus total count metadata. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The workflow needs human conversation on the PR itself before summarizing discussion or deciding whether follow-up is needed.

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

- Line-level review discussion attached to changed files; use connector.gh.pr.review_comments for code-anchored comments.
- Submitted review decisions such as APPROVED or CHANGES_REQUESTED; use connector.gh.pr.reviews for review verdicts.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.pr`](pr.md): Parent PR snapshot probe that omits conversation thread details
- [`connector.gh.pr.review_comments`](pr-review-comments.md): Sibling probe for line-level code review comments instead of top-level conversation comments
- [`connector.gh.pr.reviews`](pr-reviews.md): Sibling probe for submitted review decisions rather than free-form conversation comments

## Inspect next

- connector.gh.pr.review_comments
- connector.gh.pr.reviews
- connector.gh.pr.timeline

## Exact machine contract

Use `ordo-help operation gh.pr.comments --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_comments_step

Inspect the top-level pull request conversation thread with one explicit limit and register the resulting comment list.

```yaml
  - name: load-pr-comments
    uses: gh.pr.comments
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_comments
```
