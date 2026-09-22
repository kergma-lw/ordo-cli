# gh.actions.run

Observe an exact Actions attempt by run or check suite; omitted attempt pins the latest observed attempt. PR SHAs are API observations, not immutable event snapshots.

Use this when a workflow needs to inspect or change GitHub state. In practice: observe an exact Actions attempt by run or check suite; omitted attempt pins the latest observed attempt. PR SHAs are API observations, not immutable event snapshots.

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
  "check_suite_id": "integer",
  "repository": "string",
  "run_id": "integer"
}
```

## Outputs

```json
{
  "check_suite_id": "integer",
  "conclusion": "string",
  "created_at": "string",
  "event": "string",
  "found": "boolean",
  "head_branch": "string",
  "head_sha": "string",
  "pull_requests": [
    {
      "base_sha": "string",
      "head_sha": "string",
      "number": "integer"
    }
  ],
  "repository": "string",
  "run_attempt": "integer",
  "run_id": "integer",
  "run_started_at": "string",
  "status": "string",
  "updated_at": "string",
  "url": "string",
  "workflow_id": "integer",
  "workflow_path": "string"
}
```

## Authoring contract

Observe one GitHub Actions run attempt, selected by a run ID or a check suite's direct Actions association.

- Supply exactly one non-null positive integer run_id or check_suite_id. Optional positive integer attempt selects that numbered attempt; omitted/null attempt reads the latest observed run_attempt, then retrieves the pinned numbered attempt. Booleans are not integer identifiers.
- repository is optional and nullable: explicit valid literal ASCII OWNER/REPO overrides bootstrapped connector_contexts.gh.repository; omitted/null uses context. Malformed explicit values fail without fallback; no resolved target is input_error. Bootstrap requires an available authenticated gh CLI with repository access on github.com. Context is a default, not an authorization allowlist.
- For check_suite_id, resolve the REST suite node then query GraphQL CheckSuite.workflowRun directly, validating repository, node type, suite identity and backreference. No repository-wide run scan is used. A validated null association returns found=false, requested check_suite_id, repository, pull_requests=[], and all other run fields null. Missing nodes/fields or GraphQL errors fail, not normal absence.
- On found=true, outputs include repository, run_id, check_suite_id, run_attempt, workflow_id, workflow_path, event, status, conclusion, head_sha, head_branch, url, created_at, updated_at, run_started_at, and pull_requests with number/head_sha/base_sha. Optional API facts remain null; missing pull_requests becomes []. Present SHAs are full hexadecimal values. Output run_attempt becomes the explicit attempt input to gh.actions.run.jobs.
- Invalid selectors, attempt or repository resolution produce input_error. API/transport failures, malformed responses and repository/run/attempt/suite mismatches produce actions_run_unavailable with reason diagnostics and raw request evidence. HTTP 404 is not found=false; shared bootstrap failures can precede operation execution.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Run triggering, reruns, cancellation, polling, log retrieval, required-job selection, or merge policy. This is read-only observation.
- A tested-SHA attestation or immutable event snapshot: PR head/base SHAs are API observations, not proof of worker checkout. Latest-then-pinned retrieval is non-atomic and does not promise the newest attempt at return time.

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
- `actions_run_unavailable`

## Requirements

- None

## Example inputs

### `gh.actions.run`

```json
{
  "attempt": "integer",
  "check_suite_id": "integer",
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
          "check_suite_id": "integer",
          "repository": "string",
          "run_id": "integer"
        },
        "reference": "gh.actions.run"
      }
    ],
    "failure_modes": [
      "input_error",
      "actions_run_unavailable"
    ],
    "inputs": {
      "attempt": "integer",
      "check_suite_id": "integer",
      "repository": "string",
      "run_id": "integer"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "actions.run",
    "outputs": {
      "check_suite_id": "integer",
      "conclusion": "string",
      "created_at": "string",
      "event": "string",
      "found": "boolean",
      "head_branch": "string",
      "head_sha": "string",
      "pull_requests": [
        {
          "base_sha": "string",
          "head_sha": "string",
          "number": "integer"
        }
      ],
      "repository": "string",
      "run_attempt": "integer",
      "run_id": "integer",
      "run_started_at": "string",
      "status": "string",
      "updated_at": "string",
      "url": "string",
      "workflow_id": "integer",
      "workflow_path": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Observe an exact Actions attempt by run or check suite; omitted attempt pins the latest observed attempt. PR SHAs are API observations, not immutable event snapshots.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "actions.run",
  "reference": "gh.actions.run",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
