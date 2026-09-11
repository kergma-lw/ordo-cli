# GitHub pull request inspection probe model

## Public references

- `gh.pr`
- `gh.pr.comments`
- `gh.pr.reviews`
- `gh.pr.review_comments`
- `gh.pr.checks`
- `gh.pr.timeline`
- `gh.pr.diff`

## Kind

- `probe`

## Mental model

- This family exposes orthogonal read surfaces for one pull request.
- The neighboring [gh.pr.list](gh-pr-list.md) probe observes a filtered candidate collection before detailed by-number inspection; its inputs and full-traversal semantics are separate from this shared inspection shape.
- The neighboring [gh.pr.create](gh-pr-create.md) action performs a mandatory exact open-duplicate check and one creation submission; it does not find-or-reuse or apply closed-history policy.
- It separates metadata, discussion, review, CI, lifecycle, and change-content concerns instead of hiding them inside one opaque digest response.
- It stays read-only and does not encode merge policy or workflow decisions.
- This inspection list is distinct from the separate `gh.pr.merge` action and `gh.pr.merge.request` probe modeled in [asynchronous merge](gh-pr-merge.md); the entire `gh.pr.*` namespace is not read-only.

## Shared input shape

- `repository: string`
- `pull_number: integer`
- `limit: integer` optional on list-style probes, including `gh.pr.diff`

## `gh.pr` output shape

```json
{
  "number": 2832,
  "repository": "go-vikunja/vikunja",
  "title": "fix: normalize reminder scheduling for recurring tasks",
  "body": "...",
  "author": {
    "login": "alice"
  },
  "state": "open",
  "draft": false,
  "url": "https://github.com/go-vikunja/vikunja/pull/2832",
  "created_at": "2026-07-28T10:00:00Z",
  "updated_at": "2026-07-29T12:00:00Z",
  "base_ref": "main",
  "head_ref": "fix/reminder-scheduling",
  "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "head_repository": "go-vikunja/vikunja",
  "base_repository": "go-vikunja/vikunja",
  "base_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "merged": false,
  "merged_at": null,
  "merge_commit_sha": null,
  "test_merge_sha": "cccccccccccccccccccccccccccccccccccccccc",
  "test_merge_head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "test_merge_base_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "test_merge_state": "verified",
  "stack_state": "standalone",
  "stack": null,
  "mergeable": true,
  "mergeable_state": "unstable",
  "review_decision": "CHANGES_REQUESTED",
  "additions": 184,
  "deletions": 58,
  "changed_files": 8,
  "commits_count": 7
}
```

## `gh.pr.comments` output shape

- `pull_ref: string`
- `total_count: integer`
- `comments: [object]`
- each comment exposes at least:
  - `id`
  - `author`
  - `body`
  - `created_at`
  - `updated_at`
  - `url`

## `gh.pr.reviews` output shape

- `pull_ref: string`
- `total_count: integer`
- `reviews: [object]`
- each review exposes at least:
  - `id`
  - `author`
  - `state`
  - `body`
  - `submitted_at`
  - `commit_id`
  - `url`

## `gh.pr.review_comments` output shape

- `pull_ref: string`
- `total_count: integer`
- `comments: [object]`
- each review comment exposes at least:
  - `id`
  - `author`
  - `body`
  - `path`
  - `commit_id`
  - `original_commit_id`
  - `line`
  - `original_line`
  - `side`
  - `in_reply_to_id`
  - `created_at`
  - `updated_at`
  - `url`

## `gh.pr.checks` output shape

Inputs extend the PR identity with optional `target` (`head`, the default, or `test_merge`) and optional full hexadecimal `expected_head_sha`. This pin compares against H, never M.

The following is a compact head-target projection with two explicit successful checks, not a required-check policy decision:

```json
{
  "pull_ref": "go-vikunja/vikunja#2832",
  "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "base_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "head_repository": "go-vikunja/vikunja",
  "base_repository": "go-vikunja/vikunja",
  "target": "head",
  "expected_head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "test_merge_sha": null,
  "test_merge_head_sha": null,
  "test_merge_base_sha": null,
  "test_merge_state": "not_requested",
  "sha_evidence": "api_attached_commit",
  "complete": true,
  "statuses_complete": true,
  "check_runs_complete": true,
  "overall_state": "success",
  "total_count": 2,
  "success_count": 2,
  "failed_count": 0,
  "pending_count": 0,
  "skipped_count": 0,
  "neutral_count": 0,
  "unknown_count": 0,
  "checks": [
    {
      "name": "Test / api-build",
      "kind": "check_run",
      "status": "completed",
      "conclusion": "success",
      "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "sha_source": "check_run.head_sha",
      "url": "https://github.com/..."
    },
    {
      "name": "lint",
      "kind": "status",
      "status": "completed",
      "conclusion": "success",
      "context": "lint",
      "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "sha_source": "combined_status.sha",
      "url": "https://github.com/..."
    }
  ]
}
```

## `gh.pr.timeline` output shape

- `pull_ref: string`
- `total_count: integer`
- `events: [object]`
- each event exposes at least:
  - `event_type`
  - `actor`
  - `created_at`
  - optional bounded event-specific facts such as `from_value`, `to_value`, or a small `payload`

## `gh.pr.diff` output shape

```json
{
  "pull_ref": "go-vikunja/vikunja#2832",
  "total_files": 2,
  "files": [
    {
      "path": "src/reminders/scheduler.py",
      "previous_path": null,
      "status": "modified",
      "additions": 18,
      "deletions": 7,
      "changes": 25,
      "patch": "@@ -41,7 +41,12 @@ ...",
      "truncated": false,
      "binary": false
    },
    {
      "path": "docs/reminders.md",
      "previous_path": "docs/notifications.md",
      "status": "renamed",
      "additions": 4,
      "deletions": 2,
      "changes": 6,
      "patch": "@@ -1,3 +1,5 @@ ...",
      "truncated": false,
      "binary": false
    }
  ]
}
```

## Modeled semantics

- `gh.pr` is the canonical metadata snapshot for one pull request and should replace issue-shaped approximation when PR-native facts matter.
- `gh.pr.comments` owns only ordinary conversation comments visible on the PR thread.
- `gh.pr.reviews` owns submitted review decisions and review summary text.
- `gh.pr.review_comments` owns line-level diff discussion, including replies.
- `gh.pr.checks` owns normalized observation of API-attached head or verified test-merge checks across check runs and commit statuses.
- `gh.pr.timeline` owns normalized lifecycle transitions such as draft conversion, review-request changes, force-pushes, base changes, labels, merge, close, and reopen events.
- `gh.pr.diff` owns normalized observation of reviewable PR change content, including file-level summaries and bounded patch-bearing payloads.

### Commit and stack identity

- H is the PR head, B the base from the same PR snapshot, and M the synthetic test merge. `test_merge_state: verified` requires the candidate commit SHA to match M and its ordered parents to equal `[B, H]`. Other observation states are `unavailable`, `identity_mismatch`, and `merged`; checks targeting head use `not_requested` for test-merge evidence.
- `merge_commit_sha` is populated as a resulting SHA only when `merged` is explicitly true. It is not a synthetic-M alias. The asynchronous request's resulting `merge_sha` is likewise distinct from M and need not equal H.
- `stack_state` is `standalone`, `stacked`, or `unknown`. Only an absent API `stack` property on a validated ordinary PR envelope means `standalone`; explicit API null means `unknown`. A valid stack object means `stacked`; malformed stack/envelope data remains unknown. Response number and base repository identity must match the requested PR; fork head repositories are allowed. The ordinary envelope validates number, state, boolean merged/draft facts, and nonempty head/base refs with full SHAs.
- Public `stack` retains the valid stack object for `stacked` and is null otherwise. The standalone/null output example represents an absent API property, not an API property explicitly set to null. Public null alone is insufficient for admission. Valid stack evidence requires `base.ref` and full `base.sha`; optional `size`, `position`, `id`, and `number` must be nonnegative integers. Merge admission rejects stacked and unknown classifications before PUT.
- Stack classification and synthetic-parent verification describe pre-read observations. Neither promises atomicity with a later mutation; SHA pinning guards H, not B or stack membership.

### Checks evidence and aggregation

- `commit_sha` is H for `head`, M for `test_merge`. `head_sha` remains H in both cases. `expected_head_sha` preserves the optional caller pin. A mismatched pin fails before check retrieval; test-merge unavailability never silently selects head.
- Individual items additionally retain `state`, `id`, `created_at`, `updated_at`, `started_at`, `completed_at`, `app_id`, `app_slug`, `app_identity`, and `creator`. These support workflow-owned producer selection and freshness. Missing app identity is `unavailable`, not a guessed trusted producer.
- `sha_evidence: api_attached_commit` and item `sha_source` identify GitHub attachment evidence, not actual worker checkout. A workflow needing checkout proof must obtain separate evidence.
- Both source collections are paginated. `complete` is true only when `statuses_complete` and `check_runs_complete` are true, with consistent totals and identities. Pagination is not an atomic snapshot; duplicate identities or status contexts signal incompleteness rather than being silently deduplicated.
- Aggregate precedence is `incomplete`, `no_checks`, then any `failed`, `pending`, or `unknown`; an entirely successful nonempty set is `success`, an entirely skipped set is `skipped`, an entirely neutral set is `neutral`, and remaining successful/skipped/neutral mixtures are `mixed`. Counts cover every returned item and sum to `total_count`. Missing attached SHA cannot count as success.
- Successful retrieval and successful CI are different facts. Even a complete success summary does not establish authorization or prove that the workflow's required checks exist, came from trusted producers, or are fresh.

## Failure model

- `pull_not_found` means the requested repository-number pair did not resolve to a pull request visible to the connector.
- `limit_invalid` means a list-style probe received an invalid explicit limit.
- `checks_unavailable` means the pull request resolved but the connector could not produce the checks surface.
- `probe_failed` remains the residual normalized failure for other local breakdown.

## Boundary model

- The family owns normalized observation only.
- It does not own:
  - rendered diff presentation;
  - HTML/review-page rendering;
  - unresolved-thread heuristics;
  - merge recommendation synthesis;
  - one-shot narrative PR digest generation.
- Patch-bearing outputs, when exposed, should use connector-owned canonical structure and bounded payload shape rather than UI-shaped or transport-shaped rendering.
