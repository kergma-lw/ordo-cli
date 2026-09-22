# gh.pr.merge

Request a SHA-guarded direct async merge; save request_id for gh.pr.merge.request. Acceptance is not completion.

Use this when a workflow needs to inspect or change GitHub state. In practice: request a SHA-guarded direct async merge; save request_id for gh.pr.merge.request. Acceptance is not completion.

- Namespace: `gh`
- Kind: `action`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "expected_head_sha": "string",
  "merge_method": "string",
  "pull_number": "integer",
  "repository": "string"
}
```

## Outputs

```json
{
  "expected_head_sha": "string",
  "http_status": "integer",
  "merge_action": "string",
  "merge_method": "string",
  "merge_sha": "string",
  "merged": "boolean",
  "message": "string",
  "observed_head_sha": "string",
  "pull_number": "integer",
  "repository": "string",
  "request_compatibility": "string",
  "request_id": "string",
  "stack_scope": "string",
  "state": "string",
  "submission": "string"
}
```

## Authoring contract

Submit one direct asynchronous GitHub merge request for a standalone PR, bound to the head accepted by CI policy.

- Supply pull_number, merge_method (merge/squash/rebase), and expected_head_sha as a full 40-digit hexadecimal SHA from the accepted CI head. The repository argument is optional: a valid explicit literal ASCII OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error. Repository context is a default, not an authorization allowlist. Explicit-repository examples supply repository as workflow policy, not as an operation requirement. The context example omits repository on merge and request; its comments show profile YAML supplying the context, not a workflow YAML context declaration.
- For accepted checks on verified test-merge candidate M with base B and head H, submit expected_head_sha=H, not M. Preserve that accepted head; a freshly fetched replacement defeats the CI-to-merge binding.
- The action rejects stacked PRs and unknown scope before submission; gh.pr exposes stack_state (standalone/stacked/unknown) plus stack for authoring guards and diagnostics.
- Register the action result and save its request_id UUID with repository and pull_number for gh.pr.merge.request. submission=accepted is not completion; pending and enqueued are not merged. Already merged is distinct from already enqueued.
- An existing request is reusable only when request_compatibility=exact: merge_method, direct_merge action, and expected_head_sha all match. Different or unknown parameters are not permission to reuse or blindly retry an uncertain submission.
- Before submission, unsupported_stack rejects stacked PRs, merge_scope_unknown rejects unavailable or malformed scope, and head_mismatch reports an observed head different from expected_head_sha. An already-merged PR can be reported without a new submission or stack/head admission.
- Distinguish merge_refused (HTTP 400 refusal) from merge_api_failed (scope-read failure or submission HTTP 403/404/422). HTTP 409 denotes an existing request, not a head-mismatch reason. merge_result_unknown preserves an uncertain submission outcome; do not blindly retry.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- No atomic base or stack guarantee is provided: the head guard does not freeze base B or prevent a later stack change. Stacked and unknown scope are rejected in this first version.
- No polling, merge queue administration, admin bypass, auto-merge configuration, or branch deletion is implemented. Spontaneous GitHub automatic issue closing and repository branch configuration effects are outside the action.
- GitHub evaluates repository rules for the authenticated actor. The action requests no bypass and changes no rules, but cannot remove that actor's server-configured bypass privileges.
- Submission success does not establish merge completion. Async failure carries a message, not a structured reason code; do not infer a strict head-mismatch classification from it.

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

## Effects

- submit a direct asynchronous GitHub merge after observing a standalone PR; stack/base observation is not atomic

## Failure modes

- `input_error`
- `unsupported_stack`
- `merge_scope_unknown`
- `head_mismatch`
- `merge_api_failed`
- `merge_refused`
- `existing_request_conflict`
- `existing_request_unknown`
- `merge_result_unknown`

## Requirements

- None

## Preflight observations

```json
[
  {
    "fields": [
      "state",
      "draft",
      "head_sha",
      "stack_state"
    ],
    "probe": "gh.pr",
    "with": {
      "pull_number": "{pull_number}",
      "repository": "{repository}"
    }
  }
]
```

## Invalidated observations

- `gh.pr.*`
- `gh.issue`
- `gh.project.issue`

## Example inputs

### `gh.pr.merge`

```json
{
  "expected_head_sha": "6358cd125586d9def8c3e5943f23506202da81cc",
  "merge_method": "squash",
  "pull_number": 42,
  "repository": "octocat/Hello-World"
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
    "effects": [
      "submit a direct asynchronous GitHub merge after observing a standalone PR; stack/base observation is not atomic"
    ],
    "examples": [
      {
        "inputs": {
          "expected_head_sha": "6358cd125586d9def8c3e5943f23506202da81cc",
          "merge_method": "squash",
          "pull_number": 42,
          "repository": "octocat/Hello-World"
        },
        "reference": "gh.pr.merge"
      }
    ],
    "failure_modes": [
      "input_error",
      "unsupported_stack",
      "merge_scope_unknown",
      "head_mismatch",
      "merge_api_failed",
      "merge_refused",
      "existing_request_conflict",
      "existing_request_unknown",
      "merge_result_unknown"
    ],
    "inputs": {
      "expected_head_sha": "string",
      "merge_method": "string",
      "pull_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [
      "gh.pr.*",
      "gh.issue",
      "gh.project.issue"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "pr.merge",
    "outputs": {
      "expected_head_sha": "string",
      "http_status": "integer",
      "merge_action": "string",
      "merge_method": "string",
      "merge_sha": "string",
      "merged": "boolean",
      "message": "string",
      "observed_head_sha": "string",
      "pull_number": "integer",
      "repository": "string",
      "request_compatibility": "string",
      "request_id": "string",
      "stack_scope": "string",
      "state": "string",
      "submission": "string"
    },
    "preflight_observations": [
      {
        "fields": [
          "state",
          "draft",
          "head_sha",
          "stack_state"
        ],
        "probe": "gh.pr",
        "with": {
          "pull_number": "{pull_number}",
          "repository": "{repository}"
        }
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Request a SHA-guarded direct async merge; save request_id for gh.pr.merge.request. Acceptance is not completion.",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "pr.merge",
  "reference": "gh.pr.merge",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
