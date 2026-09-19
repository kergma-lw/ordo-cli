# GitHub Actions run observation model

## Public surfaces

| Reference | Kind | Observation |
| --- | --- | --- |
| `gh.actions.run` | probe | One numbered attempt selected by run or check suite |
| `gh.actions.run.jobs` | probe | All jobs for an explicitly numbered run attempt |

`gh.actions` is only a namespace segment. The [requirements](../../requirements/connector/gh-actions-run.md) define observation boundaries and the [shared repository identity contract](../../requirements/connector/gh-repository-identity.md) defines the repository operand.

## Inputs and bootstrap

Both probes accept optional nullable `repository: string`, resolved from explicit valid `OWNER/REPO` or bootstrapped `connector_contexts.gh.repository`. Explicit invalid input never falls back; a different explicit target can produce a repository-override warning. No resolved target is `input_error`. Bootstrap supplies GitHub CLI availability, authentication, and connector context; repository context grants no authorization. Transport uses `gh api` against `github.com` with official REST API headers and a read-only GraphQL query.

`gh.actions.run` accepts nullable `run_id: integer`, `check_suite_id: integer`, and `attempt: integer`. Exactly one selector must be non-null; every supplied integer must be positive and not boolean. Omitted/null attempt means latest observed, then pinned. `gh.actions.run.jobs` accepts required positive non-boolean `run_id: integer` and `attempt: integer`; it has no latest-attempt default or caller limit.

## Run resolution

1. Resolve repository and validate selectors.
2. For a suite selector, read `repos/{repository}/check-suites/{check_suite_id}` to bind numeric ID and node ID, then query GraphQL `node(id: ...)` as `CheckSuite` with `repository.nameWithOwner` and `workflowRun { databaseId checkSuite { id } }`. Validate types, repository and backreference. Explicit null association returns normal absence; no repository-wide run scan is used.
3. If attempt is absent, read `repos/{repository}/actions/runs/{run_id}` and validate identity to retain its `run_attempt` and suite ID.
4. Read `repos/{repository}/actions/runs/{run_id}/attempts/{attempt}` and validate run, repository, attempt, and known suite identity. The suite route also checks `check_suite_node_id`.

The final numbered-attempt response supplies outputs, not the earlier latest-run response. A rerun can begin between reads without changing which numbered attempt is returned. Pinning is not an atomic snapshot or a freshness guarantee.

## Run output shape

| Fields | Meaning |
| --- | --- |
| `repository`, `found` | Resolved repository and whether the suite/run association yielded an observed run |
| `run_id`, `check_suite_id`, `run_attempt` | Positive identities on a found run; output uses `run_attempt`, not `attempt` |
| `workflow_id` | Nullable positive workflow ID |
| `workflow_path`, `event`, `status`, `conclusion` | Nullable API facts; `workflow_path` maps API `path` |
| `head_sha`, `head_branch` | Nullable API head facts; a present SHA is full hexadecimal |
| `url` | Nullable API `html_url` |
| `created_at`, `updated_at`, `run_started_at` | Nullable API timestamp strings |
| `pull_requests` | List of positive `number` and nullable full `head_sha` / `base_sha` |

Missing optional facts stay null; missing `pull_requests` becomes `[]`. A validated null suite association yields `found: false`, preserves repository and requested suite ID, uses `pull_requests: []`, and leaves all other fields null. HTTP 404, missing GraphQL nodes, omitted association fields, and GraphQL errors do not yield normal absence.

PR SHA values are current API observations, not immutable event snapshots. No output asserts the actually tested SHA, worker checkout, trusted producer, required-job satisfaction, or merge policy.

## Jobs traversal and output shape

Read `repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100&page=N`, beginning at page 1. Validate a nonnegative stable `total_count`, exact page sizes, and official API Link relations consistent with the expected pages. Only the owner and repository path segments are compared case-insensitively as ASCII repository identity; the host, remaining path syntax, and numeric identities remain exact, with no percent-encoded aliases accepted. Requests retain the resolved repository spelling and are constructed locally. Traversal is bounded to 100 pages; exceeding the bound fails. Missing or contradictory next links, duplicate relations/IDs, changed totals, wrong run/attempt identities, malformed payloads, and incomplete pages fail rather than return a partial success.

Success returns `repository: string`, `run_id: integer`, `run_attempt: integer`, `items: [object]`, `count: integer`, and `complete: true`. Count equals the number of observed items, including zero. Each item exposes:

- `job_id`: positive integer;
- `check_run_id`: nullable positive integer extracted only from a validated official API `check_run_url` with matching repository identity (ASCII case-insensitive owner/repository segments), exact remaining path syntax and host, and no extra URL components or percent-encoded aliases;
- `name`, `status`, `conclusion`, `head_sha`, `url`, `started_at`, `completed_at`: nullable strings, with a full hexadecimal SHA when present; `url` maps API `html_url`.

The check-run bridge is `gh.pr.checks.checks[].check_suite_id` → `gh.actions.run.check_suite_id`, then found run `run_id` and `run_attempt` → jobs inputs `run_id` and `attempt`. Jobs' `check_run_id` can correlate back to check-run item `id`. Null identities must remain unavailable; legacy statuses have no suite bridge. No logs or display URLs are parsed for identity.

Completeness means this traversal passed its consistency checks, not that job state was frozen across requests. No cross-probe atomicity, polling, rerun, cancellation, logs, tested-SHA attestation, or workflow acceptance policy is modeled.

## Failure and mode model

- `input_error`: repository or selector/attempt validation failure.
- `actions_run_unavailable`: run transport, GraphQL, response-shape, or identity failure.
- `actions_jobs_unavailable`: jobs transport, response-shape, identity, or completeness failure.
- Diagnostics use `probe.gh_actions_run` or `probe.gh_actions_run.jobs` prefixes with `invalid_input`, `request_failed`, or `invalid_response`; shared repository diagnostics add repository-specific reasons. Raw request evidence is retained. Shared bootstrap failures can precede operation execution.

These are ordinary read-only probes in `check`, `review`, `plan`, `run`, `explain`, and `next`, with no new engine-mode semantics. Their public metadata, features, search routes, and verified describe examples teach the same observation contract.
