# GitHub Actions run observation requirements

## Role and boundary

- `gh.actions.run`, `gh.actions.run.jobs`, and `gh.actions.run.search` are read-only probes for one Actions run attempt, its jobs, and a bounded correlated workflow-run collection respectively. `gh.actions` is a namespace segment, not an executable operation.
- These probes expose GitHub API observations, not a tested-SHA attestation, immutable event snapshot, required-job selection, trusted-producer decision, or merge approval policy. PR head/base SHAs reported by the API do not prove the worker checkout.
- They do not trigger, rerun, cancel, poll, download logs, or mutate runs. Multiple API reads are non-atomic even when an attempt is pinned and retrieval is complete.

## Inputs and bootstrap

- Both probes follow the shared [repository identity contract](gh-repository-identity.md). `repository` is optional and nullable: an explicit valid literal ASCII `OWNER/REPO` overrides bootstrapped `connector_contexts.gh.repository`; omission or null uses that context. Invalid explicit values fail without fallback; no resolved repository is `input_error`. Context is a default, not an authorization allowlist.
- The GitHub connector must be bootstrapped with an available, authenticated `gh` CLI and access to the requested repository. These observations target `github.com` and its official API; they do not grant access or configure authentication.
- `gh.actions.run` requires exactly one non-null positive integer selector: `run_id` or `check_suite_id`. Optional positive integer `attempt` selects an exact attempt. Omitted or null `attempt` reads the latest observed attempt number and then retrieves that numbered attempt; it does not promise the newest attempt at return time.
- `gh.actions.run.jobs` requires positive integer `run_id` and explicit positive integer `attempt`. Booleans are not integer identifiers. Jobs must never silently choose the latest attempt.
- `gh.actions.run.search` requires a workflow ID or file name, exact event and ref strings, and a nonempty request ID. It lists only that workflow's runs under exact GitHub event/ref filters, then retains runs whose complete `display_title` equals the request ID. It returns all matches and never selects one.

## Association and identity

- The suite selector resolves the suite REST identity, then directly queries GraphQL `CheckSuite.workflowRun`. It must validate node type, suite identity, repository, and the workflow run's suite backreference. It must not scan repository runs or guess an association from names, display URLs, or logs.
- A validated explicit null `workflowRun` association is normal success with `found: false`. Missing nodes/fields, GraphQL errors, inaccessible objects, and malformed or contradictory identity are failures, not absence.
- Run responses must match repository, selected run, pinned attempt, and the known suite identity. The suite route also binds the suite node identity.
- `gh.pr.checks` check-run items expose nullable `check_suite_id` as the bridge into `gh.actions.run`; legacy commit statuses have null suite identity. A suite is not necessarily associated with Actions.
- Job `check_run_id` comes only from a validated official `https://api.github.com/repos/OWNER/REPO/check-runs/ID` API URL matching the repository. An absent/null link gives null identity; a malformed link fails. This is not log parsing or display-URL inference.

## Outputs

- `gh.actions.run` exposes `repository`, `found`, `run_id`, `check_suite_id`, `run_attempt`, `workflow_id`, `workflow_path`, `event`, `status`, `conclusion`, `head_sha`, `head_branch`, `url`, `created_at`, `updated_at`, `run_started_at`, and `pull_requests` items containing `number`, `head_sha`, and `base_sha`.
- On a found run, run ID, suite ID, and attempt are positive integers; optional API facts remain null when unavailable. SHA values, when present, must be full hexadecimal commit SHAs. Missing `pull_requests` yields an empty list; this list is an API association observation, not event-time attestation.
- For `found: false`, retain resolved `repository` and requested `check_suite_id`, set `pull_requests: []`, and set all other run fields to null, including `run_attempt` even if `attempt` was supplied.
- `gh.actions.run.jobs` exposes `repository`, `run_id`, `run_attempt`, `items`, `count`, and `complete`. Each item contains positive `job_id`, nullable `check_run_id`, and nullable `name`, `status`, `conclusion`, `head_sha`, `url`, `started_at`, and `completed_at`.
- Jobs success requires complete traversal with consistent totals, valid pagination links, unique job IDs, and matching run/attempt identity for every job. Empty success is `items: []`, `count: 0`, `complete: true`; it is not successful CI. Partial retrieval must fail rather than publish successful incomplete evidence.

## Failures and discovery

- Invalid selectors, attempt, or repository resolution fail as `input_error`.
- Run request failures, malformed responses, GraphQL errors, or identity mismatch fail as `actions_run_unavailable`; the jobs counterpart is `actions_jobs_unavailable`, including incomplete/inconsistent pagination and traversal limits. HTTP not-found is not `found: false`.
- Shared connector bootstrap failures remain distinct from operation-local failure modes. Raw transport evidence and reason diagnostics support investigation, not workflow policy inference.
- Publish both probes through operation metadata, `features`, search, and `describe`, with neighboring checks/family guidance and canonical verified examples. Describe readiness includes inputs, outputs, failures, bootstrap, read-only boundaries, completeness, and non-atomicity.
- All runtime modes (`check`, `review`, `plan`, `run`, `explain`, `next`) retain their existing probe semantics; these additions require no new scheduling, policy, or execution-mode behavior. Runtime modes that observe probes receive the same contract and failures.
