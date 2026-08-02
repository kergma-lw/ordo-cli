# GitHub pull request inspection probe requirements

## Role

- `gh.pr` is the canonical public `gh` probe for one pull request snapshot.
- `gh.pr.comments` is the public `gh` probe for the regular conversation comments attached to one pull request.
- `gh.pr.reviews` is the public `gh` probe for submitted pull request review events.
- `gh.pr.review_comments` is the public `gh` probe for line-level review comments attached to one pull request diff.
- `gh.pr.checks` is the public `gh` probe for normalized continuous-integration state on one pull request head.
- `gh.pr.timeline` is the public `gh` probe for normalized pull request lifecycle events.
- `gh.pr.diff` is the public `gh` probe for normalized pull-request change-content observation.

## Probe split rule

- Pull request inspection must not be modeled as an overload of `gh.issue` because review state, line comments, checks, and timeline events are distinct pull-request concerns.
- Pull request inspection must not collapse into one monolithic `gh.pr.digest` probe.
- The public surface should stay orthogonal across:
  - PR metadata;
  - regular conversation comments;
  - submitted review decisions;
  - line-level review discussion;
  - CI/check state;
  - lifecycle events;
  - change content.

## Required questions

- `gh.pr` must answer which stable pull-request facts are true for one requested pull request.
- `gh.pr.comments` must answer which regular conversation comments exist on one requested pull request.
- `gh.pr.reviews` must answer which submitted review events exist on one requested pull request.
- `gh.pr.review_comments` must answer which line-level review comments exist on one requested pull request.
- `gh.pr.checks` must answer which normalized check outcomes currently apply to one requested pull request head.
- `gh.pr.timeline` must answer which normalized lifecycle events belong to one requested pull request.
- `gh.pr.diff` must answer which reviewable file and patch changes belong to one requested pull request.

## Required inputs

- Every probe in this family requires:
  - `repository`
  - `pull_number`
- `repository` must use `OWNER/REPO` form.
- `pull_number` must be a positive integer.
- `limit` is optional for comment-, review-, timeline-, and diff-list probes.
- When present, `limit` must be a positive bounded integer.

## Output contract

- `gh.pr` must return at least:
  - `number`
  - `repository`
  - `title`
  - `body`
  - `author`
  - `state`
  - `draft`
  - `url`
  - `created_at`
  - `updated_at`
  - `base_ref`
  - `head_ref`
  - `head_sha`
  - `mergeable`
  - `mergeable_state`
  - `review_decision`
  - `additions`
  - `deletions`
  - `changed_files`
  - `commits_count`
- `gh.pr.comments`, `gh.pr.reviews`, `gh.pr.review_comments`, and `gh.pr.timeline` must return:
  - `pull_ref`
  - `total_count`
  - one ordered list payload for the relevant entity class
- `gh.pr.comments` items must expose stable conversation-comment facts such as identity, author, body, timestamps, and URL.
- `gh.pr.reviews` items must expose stable submitted-review facts such as identity, reviewer, state, body, submitted time, commit identity, and URL.
- `gh.pr.review_comments` items must expose stable line-comment facts such as identity, author, body, path, line metadata, reply linkage, timestamps, and URL.
- `gh.pr.diff` must return at least:
  - `pull_ref`
  - `total_files`
  - one ordered `files` list
- Each `gh.pr.diff` file item must expose stable change-content facts such as:
  - `path`
  - `previous_path` when applicable
  - `status`
  - `additions`
  - `deletions`
  - `changes`
  - `patch` when textual patch content is available
  - `truncated`
  - `binary`
- `gh.pr.checks` must return at least:
  - `pull_ref`
  - `head_sha`
  - `overall_state`
  - `total_count`
  - `success_count`
  - `failed_count`
  - `pending_count`
  - `skipped_count`
  - `checks`
- Each `gh.pr.checks` item must expose stable normalized facts such as:
  - `name`
  - `kind`
  - `status`
  - `conclusion`
  - `url` or `context` when available
- `gh.pr.timeline` events must expose stable lifecycle facts such as:
  - `event_type`
  - `actor`
  - `created_at`
  - bounded event payload fields relevant to that event family

## Normalization rules

- Output fields must be connector-owned canonical names rather than raw GitHub transport names.
- `gh.pr.comments` and `gh.pr.review_comments` must remain separate because ordinary conversation comments and line-level diff comments are different semantic surfaces.
- `gh.pr.reviews` must expose review-event state separately from line-comment payloads.
- `gh.pr.diff` must expose normalized change-content facts rather than rendered review UI or arbitrary raw transport payloads.
- `gh.pr.checks` must normalize legacy commit statuses and check runs into one stable result shape without exposing transport-specific stitching as workflow burden.
- `gh.pr.timeline` must publish normalized event families rather than a free-form passthrough of every raw GitHub timeline object.

## Failure contract

- Missing pull requests must fail explicitly as `pull_not_found`.
- Invalid limits must fail explicitly as `limit_invalid` on probes that accept `limit`.
- Check retrieval failures that are specific to `gh.pr.checks` should remain distinct as `checks_unavailable`.
- Any remaining implementation-local breakdown must normalize to `probe_failed`.

## Boundary contract

- These probes are observation surfaces only.
- They must not encode merge approval policy, unresolved-thread heuristics, or workflow next-step decisions.
- They may expose normalized pull-request change-content facts, including file-level diff summaries and bounded patch text, when those facts are part of the reviewable pull-request artifact.
- They must not absorb rendered diff presentation, HTML-oriented review rendering, one-shot narrative digest synthesis, or arbitrary passthrough of raw GitHub response shapes.
- `gh.pr.timeline` should expose lifecycle facts, not a generic event archive for arbitrary downstream scraping.

## Discovery rule

- The public contract should be discoverable through `ordo-help operation gh.pr` and the sibling `gh.pr.*` operations.
- Discovery material should make clear that this family is the canonical public PR inspection surface.
