# gh.actions.run.jobs

Observe all jobs for an exact Actions run attempt; fail on incomplete or inconsistent pagination.

Use this when a workflow needs to inspect or change GitHub state. In practice: observe all jobs for an exact Actions run attempt; fail on incomplete or inconsistent pagination.

- Namespace: `gh`
- Kind: `probe`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "attempt": "integer",
  "repository": "string",
  "run_id": "integer"
}
```

## Outputs

```json
{
  "complete": "boolean",
  "count": "integer",
  "items": [
    {
      "check_run_id": "integer",
      "completed_at": "string",
      "conclusion": "string",
      "head_sha": "string",
      "job_id": "integer",
      "name": "string",
      "started_at": "string",
      "status": "string",
      "url": "string"
    }
  ],
  "repository": "string",
  "run_attempt": "integer",
  "run_id": "integer"
}
```

## Authoring contract

Observe the complete job collection for one explicitly numbered GitHub Actions run attempt.

- Supply required positive integer run_id and explicit positive integer attempt, normally from gh.actions.run outputs run_id and run_attempt. There is no latest-attempt default or caller limit; booleans are invalid identifiers.
- repository is optional and nullable: explicit valid literal ASCII OWNER/REPO overrides bootstrapped connector_contexts.gh.repository; omitted/null uses context. Malformed explicit values fail without fallback; no resolved target is input_error. Bootstrap requires an available authenticated gh CLI with repository access on github.com. Context is a default, not an authorization allowlist.
- Outputs are repository, run_id, run_attempt, items, count and complete=true. Each item contains positive job_id, nullable check_run_id, and nullable name/status/conclusion/head_sha/url/started_at/completed_at. Present head_sha is a full hexadecimal SHA. Empty retrieval is items=[], count=0, complete=true, not successful CI.
- check_run_id is extracted only from a validated official https://api.github.com/repos/OWNER/REPO/check-runs/ID API check_run_url matching repository, not from logs or display URLs. Missing/null link gives null identity; malformed or mismatched links fail. Correlate this ID with gh.pr.checks check-run item id, whose check_suite_id supplies the suite-to-run bridge.
- Traverse attempt-scoped pages of 100 jobs, up to 100 pages, requiring stable total_count, exact page sizes, valid official API Link relations, unique job IDs and matching run/attempt per job. count equals len(items). Incomplete or inconsistent traversal fails rather than publishing partial success.
- Invalid repository/run_id/attempt is input_error. API/transport, malformed response, identity, invalid link, changing totals, duplicate IDs, missing pages or page-bound failures are actions_jobs_unavailable with reason diagnostics and raw evidence. Shared bootstrap failures can precede operation execution.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Selecting the latest attempt implicitly, triggering, rerunning, cancelling, polling, downloading logs, choosing required jobs, or enforcing merge policy; this is read-only observation.
- Treating complete as an atomic snapshot, CI success, immutable event-time data, or tested-SHA attestation. Cross-page and cross-probe observations are non-atomic and do not prove worker checkout.

### gh_actions_direct

Observe a known run, then pass its registered run_id and latest observed run_attempt to pinned jobs. Require complete collection before publishing every job; count=0 is valid. Exact YAML executes with normalized fixtures only: this verifies workflow handoff, not HTTP source acquisition, GraphQL association, pagination, worker checkout, atomic snapshots, or merge policy.

```yaml
version: 0
workflow: inspect-actions
inputs:
  repository: {}
  run_id: {}
blocks:
  - steps:
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          run_id: inputs.run_id
        register: observed
      - name: require-found-run
        gate: step.observed.outputs.found | eq(true)
      - name: observe-pinned-jobs
        uses: gh.actions.run.jobs
        with:
          repository: inputs.repository
          run_id: step.observed.outputs.run_id
          attempt: step.observed.outputs.run_attempt
        register: jobs
      - name: require-complete-jobs
        gate: step.jobs.outputs.complete | eq(true)
      - name: publish-observation
        publish:
          run_id: step.observed.outputs.run_id
          run_attempt: step.observed.outputs.run_attempt
          items: step.jobs.outputs.items
          count: step.jobs.outputs.count
          complete: step.jobs.outputs.complete

```

### gh_actions_bridge

Read complete PR checks, select check runs by explicit check_suite_id (several checks may share a suite), resolve the suite through gh.actions.run, gate on found, and pass registered run_id/run_attempt to complete jobs. No run ID is guessed from a check ID or URL. Exact YAML executes with normalized fixtures only: this verifies workflow handoff, not HTTP source acquisition, GraphQL association, pagination, worker checkout, atomic snapshots, or merge policy.

```yaml
version: 0
workflow: inspect-actions
inputs:
  repository: {}
  pull_number: {}
  check_suite_id: {}
blocks:
  - steps:
      - name: inspect-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'head'
        register: checks
      - name: require-complete-checks
        gate: step.checks.outputs.complete | eq(true)
      - name: require-suite-selector
        gate: inputs.check_suite_id | is_integer
      - name: select-suite-checks
        value: step.checks.outputs.checks | only(kind="check_run") | only(check_suite_id=inputs.check_suite_id)
        register: selected
      - name: require-selected-suite
        gate: step.selected.outputs.value | length | ne(0)
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          check_suite_id: inputs.check_suite_id
        register: observed
      - name: require-found-run
        gate: step.observed.outputs.found | eq(true)
      - name: observe-pinned-jobs
        uses: gh.actions.run.jobs
        with:
          repository: inputs.repository
          run_id: step.observed.outputs.run_id
          attempt: step.observed.outputs.run_attempt
        register: jobs
      - name: require-complete-jobs
        gate: step.jobs.outputs.complete | eq(true)
      - name: publish-observation
        publish:
          run_id: step.observed.outputs.run_id
          run_attempt: step.observed.outputs.run_attempt
          items: step.jobs.outputs.items
          count: step.jobs.outputs.count
          complete: step.jobs.outputs.complete

```

### gh_actions_null_suite

The same bridge gates before run lookup when the suite selector is null. Nullable check_suite_id is normal; it cannot identify an Actions run. Exact YAML executes with normalized fixtures only: this verifies workflow handoff, not HTTP source acquisition, GraphQL association, pagination, worker checkout, atomic snapshots, or merge policy.

```yaml
version: 0
workflow: inspect-actions
inputs:
  repository: {}
  pull_number: {}
  check_suite_id: {}
blocks:
  - steps:
      - name: inspect-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'head'
        register: checks
      - name: require-complete-checks
        gate: step.checks.outputs.complete | eq(true)
      - name: require-suite-selector
        gate: inputs.check_suite_id | is_integer
      - name: select-suite-checks
        value: step.checks.outputs.checks | only(kind="check_run") | only(check_suite_id=inputs.check_suite_id)
        register: selected
      - name: require-selected-suite
        gate: step.selected.outputs.value | length | ne(0)
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          check_suite_id: inputs.check_suite_id
        register: observed
      - name: require-found-run
        gate: step.observed.outputs.found | eq(true)
      - name: observe-pinned-jobs
        uses: gh.actions.run.jobs
        with:
          repository: inputs.repository
          run_id: step.observed.outputs.run_id
          attempt: step.observed.outputs.run_attempt
        register: jobs
      - name: require-complete-jobs
        gate: step.jobs.outputs.complete | eq(true)
      - name: publish-observation
        publish:
          run_id: step.observed.outputs.run_id
          run_attempt: step.observed.outputs.run_attempt
          items: step.jobs.outputs.items
          count: step.jobs.outputs.count
          complete: step.jobs.outputs.complete

```

### gh_actions_no_run

The same bridge stops at the found gate when the suite has no associated Actions run (found=false). Jobs never receives a guessed run or null attempt. Exact YAML executes with normalized fixtures only: this verifies workflow handoff, not HTTP source acquisition, GraphQL association, pagination, worker checkout, atomic snapshots, or merge policy.

```yaml
version: 0
workflow: inspect-actions
inputs:
  repository: {}
  pull_number: {}
  check_suite_id: {}
blocks:
  - steps:
      - name: inspect-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'head'
        register: checks
      - name: require-complete-checks
        gate: step.checks.outputs.complete | eq(true)
      - name: require-suite-selector
        gate: inputs.check_suite_id | is_integer
      - name: select-suite-checks
        value: step.checks.outputs.checks | only(kind="check_run") | only(check_suite_id=inputs.check_suite_id)
        register: selected
      - name: require-selected-suite
        gate: step.selected.outputs.value | length | ne(0)
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          check_suite_id: inputs.check_suite_id
        register: observed
      - name: require-found-run
        gate: step.observed.outputs.found | eq(true)
      - name: observe-pinned-jobs
        uses: gh.actions.run.jobs
        with:
          repository: inputs.repository
          run_id: step.observed.outputs.run_id
          attempt: step.observed.outputs.run_attempt
        register: jobs
      - name: require-complete-jobs
        gate: step.jobs.outputs.complete | eq(true)
      - name: publish-observation
        publish:
          run_id: step.observed.outputs.run_id
          run_attempt: step.observed.outputs.run_attempt
          items: step.jobs.outputs.items
          count: step.jobs.outputs.count
          complete: step.jobs.outputs.complete

```

## Effects

- None

## Failure modes

- `input_error`
- `actions_jobs_unavailable`

## Requirements

- None

## Example inputs

### `gh.actions.run.jobs`

```json
{
  "attempt": "integer",
  "repository": "string",
  "run_id": "integer"
}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [
      "host",
      "viewer",
      "scopes",
      "repository"
    ],
    "prerequisites": [
      "gh binary available",
      "GitHub auth available"
    ]
  },
  "document_kind": "operation",
  "namespace": "gh",
  "operation": {
    "deprecated": false,
    "effects": [],
    "examples": [
      {
        "inputs": {
          "attempt": "integer",
          "repository": "string",
          "run_id": "integer"
        },
        "reference": "gh.actions.run.jobs"
      }
    ],
    "failure_modes": [
      "input_error",
      "actions_jobs_unavailable"
    ],
    "inputs": {
      "attempt": "integer",
      "repository": "string",
      "run_id": "integer"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "actions.run.jobs",
    "outputs": {
      "complete": "boolean",
      "count": "integer",
      "items": [
        {
          "check_run_id": "integer",
          "completed_at": "string",
          "conclusion": "string",
          "head_sha": "string",
          "job_id": "integer",
          "name": "string",
          "started_at": "string",
          "status": "string",
          "url": "string"
        }
      ],
      "repository": "string",
      "run_attempt": "integer",
      "run_id": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Observe all jobs for an exact Actions run attempt; fail on incomplete or inconsistent pagination.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "actions.run.jobs",
  "reference": "gh.actions.run.jobs",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
