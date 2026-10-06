# GitHub pr diff

the workflow's GitHub repository context already names the normal repository target and the workflow needs changed-file detail there for one PR number.

Probe one GitHub pull request diff as normalized changed-file summaries with patch excerpts, rename metadata, and binary/truncation signals. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The workflow needs to reason about which files changed or inspect bounded patch content without parsing raw git output itself.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `pull_number`: required.
- `limit`: optional.

## Result and boundary

- Usable result fact: `pull_ref`.
- Usable result fact: `total_files`.
- Usable result fact: `files`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Overall PR headline facts such as title, branch refs, or review decision; use connector.gh.pr for that metadata snapshot.
- Conversation or review decision surfaces; use comments, review_comments, or reviews when the workflow is about discussion rather than code changes.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.pr`](pr.md): Parent PR snapshot probe that reports change totals but not per-file diff content
- [`connector.gh.pr.review_comments`](pr-review-comments.md): Sibling probe for line-level reviewer feedback that may reference files from this diff
- [`connector.git.range`](../git/range.md): Repository-local git diff surface when the workflow needs local git ranges instead of remote PR normalization

## Inspect next

- connector.gh.pr.review_comments
- connector.git.range
- connector.gh.pr

## Exact machine contract

Use `ordo-help operation gh.pr.diff --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_diff_step

Inspect changed files and bounded diff content from one pull request before reacting to code-level changes.

```yaml
  - name: Load pull request diff
    uses: gh.pr.diff
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_diff
```
