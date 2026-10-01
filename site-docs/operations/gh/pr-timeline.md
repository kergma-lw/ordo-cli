# GitHub pr timeline

the workflow's GitHub repository context already names the normal repository target and the workflow needs lifecycle history there for one PR number.

Probe one GitHub pull request timeline as normalized lifecycle events such as ready-for-review, review requests, and base-ref changes. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The workflow needs temporal PR lifecycle facts that are not equivalent to comments, checks, or the current PR snapshot alone.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `pull_number`: required.
- `limit`: optional.

## Result and boundary

- Usable result fact: `pull_ref`.
- Usable result fact: `total_count`.
- Usable result fact: `events`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- The current PR state only; use connector.gh.pr when timeline history is unnecessary.
- Top-level discussion or submitted review verdicts; use comments or reviews for those narrower surfaces.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.pr`](pr.md): Parent PR snapshot for the current state without event history
- [`connector.gh.pr.reviews`](pr-reviews.md): Sibling probe for submitted review verdicts rather than timeline events
- [`connector.gh.pr.comments`](pr-comments.md): Sibling probe for conversation comments rather than lifecycle history

## Inspect next

- connector.gh.pr.reviews
- connector.gh.pr.comments
- connector.gh.pr

## Exact machine contract

Use `ordo-help operation gh.pr.timeline --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_timeline_step

Inspect lifecycle events from the pull request timeline with one explicit limit before summarizing history.

```yaml
  - name: load-pr-timeline
    uses: gh.pr.timeline
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_timeline
```
