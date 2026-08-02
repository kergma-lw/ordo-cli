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
- It separates metadata, discussion, review, CI, lifecycle, and change-content concerns instead of hiding them inside one opaque digest response.
- It stays read-only and does not encode merge policy or workflow decisions.

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
  "state": "OPEN",
  "draft": false,
  "url": "https://github.com/go-vikunja/vikunja/pull/2832",
  "created_at": "2026-07-28T10:00:00Z",
  "updated_at": "2026-07-29T12:00:00Z",
  "base_ref": "main",
  "head_ref": "fix/reminder-scheduling",
  "head_sha": "abc123...",
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

```json
{
  "pull_ref": "go-vikunja/vikunja#2832",
  "head_sha": "abc123...",
  "overall_state": "success",
  "total_count": 39,
  "success_count": 29,
  "failed_count": 0,
  "pending_count": 0,
  "skipped_count": 1,
  "checks": [
    {
      "name": "Test / api-build",
      "kind": "check_run",
      "status": "completed",
      "conclusion": "success",
      "url": "https://github.com/..."
    },
    {
      "name": "lint",
      "kind": "status",
      "status": "completed",
      "conclusion": "success",
      "context": "lint",
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
- `gh.pr.checks` owns normalized observation of the PR head CI surface across check runs and commit statuses.
- `gh.pr.timeline` owns normalized lifecycle transitions such as draft conversion, review-request changes, force-pushes, base changes, labels, merge, close, and reopen events.
- `gh.pr.diff` owns normalized observation of reviewable PR change content, including file-level summaries and bounded patch-bearing payloads.

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
