# GitHub pr checks

Read the checks attached to one pull request source revision before the workflow decides whether that revision is acceptable.

Observe named check results, their source revision, and whether the observation is complete; the workflow chooses what counts as acceptable.

## Use when

- Provide a pull request number. The normal repository comes from the workflow context; name another repository only when the workflow intentionally targets it.
- Use head to inspect the pull request source revision. expected_head_sha optionally requires that exact full commit ID, preventing a later source revision from silently replacing the one being assessed.
- Use complete, statuses_complete, check_runs_complete, head_sha, commit_sha, overall_state, and each check's name, producer, status, conclusion, source revision, and timestamps. Pending, failed, skipped, neutral, unknown, and empty evidence are not success; choose required checks and trusted producers explicitly.
- When the workflow accepts a source revision for merge, save head_sha and pass that saved value as gh.pr.merge.expected_head_sha. Do not substitute a later source revision.
- A check can link to a workflow run. When that link is present, gh.actions.run can read the run and gh.actions.run.jobs can read its jobs. A missing link does not decide whether the checks passed.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `pull_number`: required.
- `target`: optional.
- `expected_head_sha`: conditional.

## Result and boundary

- Usable result fact: `pull_ref`.
- Usable result fact: `head_sha`.
- Usable result fact: `base_sha`.
- Usable result fact: `head_repository`.
- Usable result fact: `base_repository`.
- Usable result fact: `target`.
- Usable result fact: `expected_head_sha`.
- Usable result fact: `commit_sha`.
- Usable result fact: `test_merge_sha`.
- Usable result fact: `test_merge_head_sha`.
- Usable result fact: `test_merge_base_sha`.
- Usable result fact: `test_merge_state`.
- Usable result fact: `test_merge_reason`.
- Usable result fact: `sha_evidence`.
- Usable result fact: `complete`.
- Usable result fact: `statuses_complete`.
- Usable result fact: `check_runs_complete`.
- Usable result fact: `overall_state`.
- Usable result fact: `total_count`.
- Usable result fact: `success_count`.
- Usable result fact: `failed_count`.
- Usable result fact: `pending_count`.
- Usable result fact: `skipped_count`.
- Usable result fact: `neutral_count`.
- Usable result fact: `unknown_count`.
- Usable result fact: `checks`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Review decisions from people; use connector.gh.pr.reviews when the workflow cares about approvals or requested changes.
- Do not use this to learn what individual jobs did inside a linked workflow run; use connector.gh.actions.run and connector.gh.actions.run.jobs when that run detail is needed.
- Branch or headline pull request facts; use connector.gh.pr for the broader snapshot.
- Protection-rule satisfaction or an atomic view of the target branch and stack. Incomplete or unavailable evidence must not be treated as accepted. This operation neither waits nor submits a merge.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.pr`](pr.md): Parent PR snapshot that supplies the head SHA and mergeability context
- [`connector.gh.actions.run`](actions-run.md): Read the workflow run linked from one check when that link is available
- [`connector.gh.actions.run.jobs`](actions-run-jobs.md): Complete job collection for that explicit run attempt
- [`connector.gh.pr.reviews`](pr-reviews.md): Sibling probe for human review decisions rather than machine status results
- [`connector.gh.pr.timeline`](pr-timeline.md): Sibling probe for lifecycle events that can explain why checks changed over time
- [`connector.gh.pr.merge`](pr-merge.md): Submit using the head identity retained from accepted CI evidence
- [`connector.gh.pr.merge.request`](pr-merge-request.md): Observe the saved merge request, not CI status

## Inspect next

- connector.gh.actions.run
- connector.gh.actions.run.jobs
- connector.gh.pr.reviews
- connector.gh.pr.timeline
- connector.gh.pr
- connector.gh.pr.merge
- connector.gh.pr.merge.request

## Exact machine contract

Use `ordo-help operation gh.pr.checks --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_checks_step

Inspect status contexts and check runs for the pull request head before merge-readiness decisions.

```yaml
  - name: load-pr-checks
    uses: gh.pr.checks
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
    register: pr_checks
```
