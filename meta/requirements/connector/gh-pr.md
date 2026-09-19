# GitHub pull request inspection probe requirements

## Role

- Repository inputs follow the shared [GitHub repository input identity](gh-repository-identity.md) contract, including literal grammar, validation ordering, and context-default boundaries.

- `gh.pr` is the canonical public `gh` probe for one pull request snapshot.
- The neighboring `gh.pr.list` probe discovers a full filtered candidate collection under its [separate list contract](gh-pr-list.md); it does not share the by-number inputs below or select the correct PR.
- The neighboring [gh.pr.create action](gh-pr-create.md) creates a PR after its own mandatory exact open-duplicate check; creation and workflow-owned closed-history policy are separate from by-number inspection.
- `gh.pr.comments` is the public `gh` probe for the regular conversation comments attached to one pull request.
- `gh.pr.reviews` is the public `gh` probe for submitted pull request review events.
- `gh.pr.review_comments` is the public `gh` probe for line-level review comments attached to one pull request diff.
- `gh.pr.checks` is the public `gh` probe for normalized continuous-integration evidence attached to one pull request head or verified synthetic test merge.
- `gh.pr.timeline` is the public `gh` probe for normalized pull request lifecycle events.
- `gh.pr.diff` is the public `gh` probe for normalized pull-request change-content observation.
- The separate `gh.pr.merge` action and `gh.pr.merge.request` observation probe follow the [asynchronous merge requirements](gh-pr-merge.md). The read-only boundary here applies to inspection probes, not every operation with a `gh.pr` prefix.

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
- `gh.pr.checks` must answer which normalized check outcomes are API-attached to the selected commit, with explicit identity evidence and retrieval completeness.
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
- `gh.pr.checks` accepts `target: head|test_merge` (default `head`) and optional `expected_head_sha`, a full 40-character hexadecimal SHA. A pin must match the observed PR head before retrieving checks; it always pins head H, including when checks target synthetic merge M.

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
  - `head_repository`
  - `base_repository`
  - `base_sha`
  - `merged`
  - `merged_at`
  - `merge_commit_sha`
  - `test_merge_sha`
  - `test_merge_head_sha`
  - `test_merge_base_sha`
  - `test_merge_state`
  - `stack_state`
  - `stack`
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
- Checks must additionally expose `base_sha`, `head_repository`, `base_repository`, `target`, `expected_head_sha`, `commit_sha`, `test_merge_sha`, `test_merge_head_sha`, `test_merge_base_sha`, `test_merge_state`, `sha_evidence`, `complete`, `statuses_complete`, `check_runs_complete`, `neutral_count`, and `unknown_count`.
- Check items must retain `state`, `sha`, `sha_source`, `id`, timestamps (`created_at`, `updated_at`, `started_at`, `completed_at`), `app_id`, `app_slug`, `app_identity`, and `creator` where available. Missing identity facts must remain unavailable rather than be invented.
- Check-run items additionally expose nullable `check_suite_id` from the API check suite identity; legacy commit statuses expose null. This is the selector bridge to [gh.actions.run](gh-actions-run.md), not proof that the suite has an associated Actions run or that any worker tested a particular SHA.
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
- `gh.pr` must separate resulting `merge_commit_sha` for an explicitly merged PR from the synthetic test merge of an open, explicitly unmerged PR. Synthetic M is verified only against the same snapshot's ordered commit parents `[B, H]`; a missing or mismatched candidate cannot fall back to head checks.
- `stack_state` is `standalone`, `stacked`, or `unknown`. Only an absent API `stack` property on a validated PR envelope establishes `standalone`; an explicitly null property is `unknown`. A valid stack object establishes `stacked`; malformed or indeterminate facts remain `unknown`. Bind the response number and base repository identity to the requested PR before trusting classification. A valid ordinary envelope requires positive integer number, supported state, boolean merged/draft facts, and head/base branches with nonempty refs and full SHAs. Fork head repositories need not equal the base repository.
- Public `stack` contains the raw normalized valid stack object only for `stacked`, otherwise null. Thus public `stack: null` does not distinguish absent API data from invalid/null API data; consumers must use `stack_state`. A valid stack requires `base.ref` and full `base.sha`, with nonnegative integer `size`, `position`, `id`, and `number` if present. Failed observations never establish standalone status.
- Check pagination must follow all pages of latest statuses and check runs and expose completeness separately for each source. Missing/inconsistent totals, duplicate identities, duplicate status contexts, and pagination drift must not yield complete success. Cross-page reads are not atomic.
- `overall_state: success` requires a complete, nonempty collection consisting entirely of explicit successful, SHA-attached results. Skipped, neutral, unknown, absent, pending, failed, or incomplete evidence must not be promoted to success. Mixed successful/skipped/neutral outcomes are `mixed`, not success.
- API-attached commit evidence (`sha_evidence: api_attached_commit`) does not prove which commit a CI worker actually checked out. Workflows own trusted producer selection, required CI selection, freshness, authorization, and any additional checkout attestation requirements.
- `gh.pr.timeline` must publish normalized event families rather than a free-form passthrough of every raw GitHub timeline object.

## Failure contract

- Missing pull requests must fail explicitly as `pull_not_found`.
- Invalid limits must fail explicitly as `limit_invalid` on probes that accept `limit`.
- Check retrieval failures that are specific to `gh.pr.checks` should remain distinct as `checks_unavailable`.
- Invalid check targets/pins, pin mismatch, attached-SHA mismatch, and unavailable or mismatched test-merge identity must fail closed as `checks_unavailable` with a specific diagnostic reason. A directly observed pin mismatch can use `head_mismatch`; an unstructured asynchronous merge failure message cannot establish that reason.
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
- Runtime-mode, discovery, and snippet verification obligations for merge-related observation changes are specified in [asynchronous merge requirements](gh-pr-merge.md). These are approved source semantics, not permission to rewrite the contract around implementation drift.
