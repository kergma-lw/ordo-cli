# gh.pr.checks

Read normalized status and check-run results from a GitHub pull request head.

Use this when a workflow needs to inspect or change GitHub state. In practice: read normalized status and check-run results from a GitHub pull request head.

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
  "expected_head_sha": "string",
  "pull_number": "integer",
  "repository": "string",
  "target": "string"
}
```

## Outputs

```json
{
  "base_repository": "string",
  "base_sha": "string",
  "check_runs_complete": "boolean",
  "checks": [
    {
      "app_id": "integer",
      "app_identity": "string",
      "app_slug": "string",
      "check_suite_id": "integer",
      "completed_at": "string",
      "conclusion": "string",
      "context": "string",
      "created_at": "string",
      "creator": "object",
      "id": "integer",
      "kind": "string",
      "name": "string",
      "sha": "string",
      "sha_source": "string",
      "started_at": "string",
      "state": "string",
      "status": "string",
      "updated_at": "string",
      "url": "string"
    }
  ],
  "commit_sha": "string",
  "complete": "boolean",
  "expected_head_sha": "string",
  "failed_count": "integer",
  "head_repository": "string",
  "head_sha": "string",
  "neutral_count": "integer",
  "overall_state": "string",
  "pending_count": "integer",
  "pull_ref": "string",
  "sha_evidence": "string",
  "skipped_count": "integer",
  "statuses_complete": "boolean",
  "success_count": "integer",
  "target": "string",
  "test_merge_base_sha": "string",
  "test_merge_head_sha": "string",
  "test_merge_reason": "string",
  "test_merge_sha": "string",
  "test_merge_state": "string",
  "total_count": "integer",
  "unknown_count": "integer"
}
```

## Authoring contract

Probe one GitHub pull request head for normalized status contexts and check runs, or select a verified test-merge candidate. Paginated API-attached evidence preserves status fidelity and commit identity for workflow-owned CI acceptance policy.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs CI readiness for one PR there by pull number.
- The workflow needs CI readiness or status context outcomes before recommending merge, rerun, or escalation steps.
- target defaults to head; target=test_merge requires verified candidate M with base B and head H. commit_sha identifies the checked API commit; head_sha remains H. Optional expected_head_sha binds the observation to H and rejects a mismatch without silently switching targets.
- Inspect complete, statuses_complete, check_runs_complete, sha_evidence, and each check's name/context, app identity, SHA source, status, conclusion, and timestamps. Pending, failed, skipped, neutral, unknown, and empty evidence are not interchangeable with success; workflow policy must choose required checks and trusted producers explicitly.
- Preserve the head from accepted CI evidence for gh.pr.merge.expected_head_sha. Checks on candidate M authorize expected H, not M; never substitute a freshly fetched head after CI acceptance.
- Check-run items expose nullable check_suite_id from API check_suite.id; legacy commit statuses use null. Pass a known suite ID to gh.actions.run for direct GraphQL association lookup, then its run_id and run_attempt to gh.actions.run.jobs as run_id and explicit attempt. A validated null Actions association is found=false, not failed CI. Jobs' check_run_id comes from a validated official API URL and can correlate back to check-run item id; this bridge adds no tested-SHA or merge-policy claim.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Review decisions from humans; use connector.gh.pr.reviews when the workflow cares about approvals or change requests.
- Branch or headline PR metadata unrelated to execution status; use connector.gh.pr for the broader snapshot.
- API-attached SHA evidence does not prove the CI worker checkout, branch-protection satisfaction, or an atomic base/stack snapshot. Pagination can drift; incomplete or unavailable evidence must not be treated as passing CI. No polling or merge submission occurs here.

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

### gh_pr_async_merge_head

Execute this exact workflow with bounded, injected connector fixtures. Authorization defaults to false; standalone PRs require complete, SHA-pinned successful CI and one explicit unit check from app 15368. Save H for both checks and submission; the test_merge variant additionally binds candidate M to H and base B. API attachment is not proof of a worker checkout. Save the returned UUID, observe it once when present, and publish pending/failed/enqueued honestly. Only a final gh.pr observation confirms merged. Fixtures verify workflow execution and handoff, not live GitHub behavior or atomic CI freshness.

```yaml
version: 0
workflow: gh-pr-merge-head
inputs:
  repository:
    description: Explicit OWNER/REPO repository.
  pull_number:
    description: Pull request number.
  authorize_merge:
    default: false
    description: Explicit workflow authorization to submit a direct merge.
blocks:
  - steps:
      - name: require-merge-authorization
        gate: inputs.authorize_merge | eq(true)
      - name: save-head
        uses: gh.pr
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
        register: h
      - name: require-standalone-head
        gate:
          all:
            - step.h.outputs.stack_state | eq("standalone")
            - step.h.outputs.head_sha | is_string
      - name: inspect-pinned-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'head'
          expected_head_sha: step.h.outputs.head_sha
        register: ci
      - name: require-pinned-trusted-ci
        gate:
          all:
            - step.ci.outputs.complete | eq(true)
            - step.ci.outputs.statuses_complete | eq(true)
            - step.ci.outputs.check_runs_complete | eq(true)
            - step.ci.outputs.head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.expected_head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.target | eq("head")
            - step.ci.outputs.commit_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.overall_state | eq("success")
            - step.ci.outputs.checks | only(name="unit") | only(app_id=15368) | length | eq(1)
            - step.ci.outputs.checks | only(name="unit") | only(app_id=15368) | only(kind="check_run") | only(status="completed") | only(conclusion="success") | only(sha=step.ci.outputs.commit_sha) | length | eq(1)
      - name: submit-merge
        uses: gh.pr.merge
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          merge_method: 'squash'
          expected_head_sha: step.h.outputs.head_sha
        register: submission
      - name: publish-submission
        publish:
          request_id: step.submission.outputs.request_id
          submission_state: step.submission.outputs.state
      - name: observe-saved-request-once
        if: step.submission.outputs.request_id | is_string
        uses: gh.pr.merge.request
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          request_id: step.submission.outputs.request_id
        register: request
      - name: publish-request-observation
        if: step.submission.outputs.request_id | is_string
        publish:
          request_id: step.submission.outputs.request_id
          request_state: step.request.outputs.state
          request_message: step.request.outputs.message
      - name: confirm-pr
        uses: gh.pr
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
        register: final_pr
      - name: publish-confirmation
        publish:
          merged: step.final_pr.outputs.merged
          merge_commit_sha: step.final_pr.outputs.merge_commit_sha

```

### gh_pr_async_merge_test_merge

Execute this exact workflow with bounded, injected connector fixtures. Authorization defaults to false; standalone PRs require complete, SHA-pinned successful CI and one explicit unit check from app 15368. Save H for both checks and submission; the test_merge variant additionally binds candidate M to H and base B. API attachment is not proof of a worker checkout. Save the returned UUID, observe it once when present, and publish pending/failed/enqueued honestly. Only a final gh.pr observation confirms merged. Fixtures verify workflow execution and handoff, not live GitHub behavior or atomic CI freshness.

```yaml
version: 0
workflow: gh-pr-merge-test-merge
inputs:
  repository:
    description: Explicit OWNER/REPO repository.
  pull_number:
    description: Pull request number.
  authorize_merge:
    default: false
    description: Explicit workflow authorization to submit a direct merge.
blocks:
  - steps:
      - name: require-merge-authorization
        gate: inputs.authorize_merge | eq(true)
      - name: save-head
        uses: gh.pr
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
        register: h
      - name: require-standalone-head
        gate:
          all:
            - step.h.outputs.stack_state | eq("standalone")
            - step.h.outputs.head_sha | is_string
      - name: inspect-pinned-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'test_merge'
          expected_head_sha: step.h.outputs.head_sha
        register: ci
      - name: require-pinned-trusted-ci
        gate:
          all:
            - step.ci.outputs.complete | eq(true)
            - step.ci.outputs.statuses_complete | eq(true)
            - step.ci.outputs.check_runs_complete | eq(true)
            - step.ci.outputs.head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.expected_head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.target | eq("test_merge")
            - step.h.outputs.test_merge_state | eq("verified")
            - step.h.outputs.test_merge_head_sha | eq(step.h.outputs.head_sha)
            - step.h.outputs.test_merge_base_sha | eq(step.h.outputs.base_sha)
            - step.ci.outputs.test_merge_state | eq("verified")
            - step.ci.outputs.test_merge_sha | eq(step.h.outputs.test_merge_sha)
            - step.ci.outputs.test_merge_head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.test_merge_base_sha | eq(step.h.outputs.base_sha)
            - step.ci.outputs.base_sha | eq(step.h.outputs.base_sha)
            - step.ci.outputs.commit_sha | eq(step.h.outputs.test_merge_sha)
            - step.ci.outputs.overall_state | eq("success")
            - step.ci.outputs.checks | only(name="unit") | only(app_id=15368) | length | eq(1)
            - step.ci.outputs.checks | only(name="unit") | only(app_id=15368) | only(kind="check_run") | only(status="completed") | only(conclusion="success") | only(sha=step.ci.outputs.commit_sha) | length | eq(1)
      - name: submit-merge
        uses: gh.pr.merge
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          merge_method: 'squash'
          expected_head_sha: step.h.outputs.head_sha
        register: submission
      - name: publish-submission
        publish:
          request_id: step.submission.outputs.request_id
          submission_state: step.submission.outputs.state
      - name: observe-saved-request-once
        if: step.submission.outputs.request_id | is_string
        uses: gh.pr.merge.request
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          request_id: step.submission.outputs.request_id
        register: request
      - name: publish-request-observation
        if: step.submission.outputs.request_id | is_string
        publish:
          request_id: step.submission.outputs.request_id
          request_state: step.request.outputs.state
          request_message: step.request.outputs.message
      - name: confirm-pr
        uses: gh.pr
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
        register: final_pr
      - name: publish-confirmation
        publish:
          merged: step.final_pr.outputs.merged
          merge_commit_sha: step.final_pr.outputs.merge_commit_sha

```

### gh_pr_async_merge_head_context

Execute this exact workflow with bounded, injected connector fixtures. Authorization defaults to false; standalone PRs require complete, SHA-pinned successful CI and one explicit unit check from app 15368. Save H for both checks and submission; the test_merge variant additionally binds candidate M to H and base B. API attachment is not proof of a worker checkout. Save the returned UUID, observe it once when present, and publish pending/failed/enqueued honestly. Only a final gh.pr observation confirms merged. Fixtures verify workflow execution and handoff, not live GitHub behavior or atomic CI freshness. With connector_contexts.gh.repository available as a literal bootstrap value, merge and request omit repository; explicit repository overrides remain supported. PR reads and checks use an explicit input guarded to match that context. Fixtures check authored omission and context/output consistency, not real handler fallback or authentication.

```yaml
version: 0
workflow: gh-pr-merge-head-context
# Requires runtime connector_contexts.gh.repository = acme/mobile-app.
# Supply via profile YAML: connectors: {gh: {repository: acme/mobile-app}}
inputs:
  repository:
    description: Explicit OWNER/REPO repository.
  pull_number:
    description: Pull request number.
  authorize_merge:
    default: false
    description: Explicit workflow authorization to submit a direct merge.
blocks:
  - steps:
      - name: require-merge-authorization
        gate: inputs.authorize_merge | eq(true)
      - name: require-matching-repository
        gate: inputs.repository | eq("acme/mobile-app")
      - name: save-head
        uses: gh.pr
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
        register: h
      - name: require-standalone-head
        gate:
          all:
            - step.h.outputs.stack_state | eq("standalone")
            - step.h.outputs.head_sha | is_string
      - name: inspect-pinned-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'head'
          expected_head_sha: step.h.outputs.head_sha
        register: ci
      - name: require-pinned-trusted-ci
        gate:
          all:
            - step.ci.outputs.complete | eq(true)
            - step.ci.outputs.statuses_complete | eq(true)
            - step.ci.outputs.check_runs_complete | eq(true)
            - step.ci.outputs.head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.expected_head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.target | eq("head")
            - step.ci.outputs.commit_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.overall_state | eq("success")
            - step.ci.outputs.checks | only(name="unit") | only(app_id=15368) | length | eq(1)
            - step.ci.outputs.checks | only(name="unit") | only(app_id=15368) | only(kind="check_run") | only(status="completed") | only(conclusion="success") | only(sha=step.ci.outputs.commit_sha) | length | eq(1)
      - name: submit-merge
        uses: gh.pr.merge
        with:
          pull_number: inputs.pull_number
          merge_method: 'squash'
          expected_head_sha: step.h.outputs.head_sha
        register: submission
      - name: publish-submission
        publish:
          request_id: step.submission.outputs.request_id
          submission_state: step.submission.outputs.state
      - name: observe-saved-request-once
        if: step.submission.outputs.request_id | is_string
        uses: gh.pr.merge.request
        with:
          pull_number: inputs.pull_number
          request_id: step.submission.outputs.request_id
        register: request
      - name: publish-request-observation
        if: step.submission.outputs.request_id | is_string
        publish:
          request_id: step.submission.outputs.request_id
          request_state: step.request.outputs.state
          request_message: step.request.outputs.message
      - name: confirm-pr
        uses: gh.pr
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
        register: final_pr
      - name: publish-confirmation
        publish:
          merged: step.final_pr.outputs.merged
          merge_commit_sha: step.final_pr.outputs.merge_commit_sha

```

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

- `pull_not_found`
- `checks_unavailable`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.pr.checks`

```json
{
  "expected_head_sha": "string",
  "pull_number": "integer",
  "repository": "string",
  "target": "string"
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
          "expected_head_sha": "string",
          "pull_number": "integer",
          "repository": "string",
          "target": "string"
        },
        "reference": "gh.pr.checks"
      }
    ],
    "failure_modes": [
      "pull_not_found",
      "checks_unavailable",
      "probe_failed"
    ],
    "inputs": {
      "expected_head_sha": "string",
      "pull_number": "integer",
      "repository": "string",
      "target": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "pr.checks",
    "outputs": {
      "base_repository": "string",
      "base_sha": "string",
      "check_runs_complete": "boolean",
      "checks": [
        {
          "app_id": "integer",
          "app_identity": "string",
          "app_slug": "string",
          "check_suite_id": "integer",
          "completed_at": "string",
          "conclusion": "string",
          "context": "string",
          "created_at": "string",
          "creator": "object",
          "id": "integer",
          "kind": "string",
          "name": "string",
          "sha": "string",
          "sha_source": "string",
          "started_at": "string",
          "state": "string",
          "status": "string",
          "updated_at": "string",
          "url": "string"
        }
      ],
      "commit_sha": "string",
      "complete": "boolean",
      "expected_head_sha": "string",
      "failed_count": "integer",
      "head_repository": "string",
      "head_sha": "string",
      "neutral_count": "integer",
      "overall_state": "string",
      "pending_count": "integer",
      "pull_ref": "string",
      "sha_evidence": "string",
      "skipped_count": "integer",
      "statuses_complete": "boolean",
      "success_count": "integer",
      "target": "string",
      "test_merge_base_sha": "string",
      "test_merge_head_sha": "string",
      "test_merge_reason": "string",
      "test_merge_sha": "string",
      "test_merge_state": "string",
      "total_count": "integer",
      "unknown_count": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Observe paginated API-attached checks for a PR head or verified test merge; optionally bind expected_head_sha.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr.checks",
  "reference": "gh.pr.checks",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
