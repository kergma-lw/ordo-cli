# gh.pr.merge.request

Observe a saved async merge UUID once: pending, merged, enqueued, or failed. Requests expire after 24 hours; 404 is unavailable, not failure proof.

Use this when a workflow needs to inspect or change GitHub state. In practice: observe a saved async merge UUID once: pending, merged, enqueued, or failed. Requests expire after 24 hours; 404 is unavailable, not failure proof.

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
  "pull_number": "integer",
  "repository": "string",
  "request_id": "string"
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
  "pull_number": "integer",
  "repository": "string",
  "request_id": "string",
  "state": "string"
}
```

## Authoring contract

Observe one saved asynchronous GitHub merge request UUID once and report its pending, merged, failed, or enqueued state.

- Supply pull_number and request_id from the stored gh.pr.merge action result; the UUID identifies the submitted request rather than a newly fetched PR head. The repository argument is optional: a valid explicit literal ASCII OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error. The resolved repository input/context and pull_number must match the saved request's target. Explicit-repository examples supply repository as workflow policy, not as an operation requirement. The context example omits repository on merge and request; its comments show profile YAML supplying the context, not a workflow YAML context declaration.
- pending means unfinished; merged reports merge_sha; enqueued means queued, not merged. A successfully observed failed state is a successful probe observation of an unsuccessful merge, with GitHub's message preserved.
- Requests are retained for 24 hours. request_unavailable, including an expired or missing UUID (404), is unavailable evidence, not proof that the merge failed. Preserve uncertainty rather than blindly resubmitting.
- Use the request state and availability together; merged=false alone cannot distinguish pending, failed, enqueued, or unavailable evidence and is not proof of an unmerged PR. Confirm current PR completion with gh.pr when the workflow needs that fact.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- No polling, queue administration, admin bypass, or new submission occurs. Use gh.pr.merge only after CI acceptance and standalone scope admission; it rejects stacked and unknown scope and reuses only an exact matching existing request.
- The asynchronous failure message is not a structured reason code and cannot reliably establish a strict head-mismatch classification. This observation provides no atomic base or stack guarantee.

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

- None

## Failure modes

- `input_error`
- `request_unavailable`

## Requirements

- None

## Example inputs

### `gh.pr.merge.request`

```json
{
  "pull_number": 42,
  "repository": "octocat/Hello-World",
  "request_id": "12345678-1234-1234-1234-123456789abc"
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
          "pull_number": 42,
          "repository": "octocat/Hello-World",
          "request_id": "12345678-1234-1234-1234-123456789abc"
        },
        "reference": "gh.pr.merge.request"
      }
    ],
    "failure_modes": [
      "input_error",
      "request_unavailable"
    ],
    "inputs": {
      "pull_number": "integer",
      "repository": "string",
      "request_id": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "pr.merge.request",
    "outputs": {
      "expected_head_sha": "string",
      "http_status": "integer",
      "merge_action": "string",
      "merge_method": "string",
      "merge_sha": "string",
      "merged": "boolean",
      "message": "string",
      "pull_number": "integer",
      "repository": "string",
      "request_id": "string",
      "state": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Observe a saved async merge UUID once: pending, merged, enqueued, or failed. Requests expire after 24 hours; 404 is unavailable, not failure proof.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr.merge.request",
  "reference": "gh.pr.merge.request",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
