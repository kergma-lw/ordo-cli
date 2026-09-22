# gh.pr

Read pull request metadata from GitHub.

Use this when a workflow needs to inspect or change GitHub state. In practice: read pull request metadata from GitHub.

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
  "repository": "string"
}
```

## Outputs

```json
{
  "additions": "integer",
  "author": "object",
  "base_ref": "string",
  "base_repository": "string",
  "base_sha": "string",
  "body": "string",
  "changed_files": "integer",
  "commits_count": "integer",
  "created_at": "string",
  "deletions": "integer",
  "draft": "boolean",
  "head_ref": "string",
  "head_repository": "string",
  "head_sha": "string",
  "merge_commit_sha": "string",
  "mergeable": "boolean",
  "mergeable_state": "string",
  "merged": "boolean",
  "merged_at": "string",
  "number": "integer",
  "repository": "string",
  "review_decision": "string",
  "stack": "object",
  "stack_state": "string",
  "state": "string",
  "test_merge_base_sha": "string",
  "test_merge_head_sha": "string",
  "test_merge_reason": "string",
  "test_merge_sha": "string",
  "test_merge_state": "string",
  "title": "string",
  "updated_at": "string",
  "url": "string"
}
```

## Authoring contract

Probe one GitHub pull request as a typed metadata snapshot with head/base identity, a verified test-merge candidate, and stack scope. Prefer connector_contexts.gh.repository as the normal repository target; review warns when an explicit repository overrides it.

- connector_contexts.gh.repository already names the normal repository target and workflow logic now needs one PR snapshot there by pull number.
- Workflow logic needs the pull request's current headline facts before deciding which narrower PR surfaces to inspect next.
- A later step needs branch refs, draft/state flags, review decision, or change totals from one normalized PR snapshot.
- head_sha and base_sha identify head H and base B with their repositories. test_merge_state=verified means candidate M has the observed parents B then H; test_merge_sha, test_merge_head_sha, and test_merge_base_sha retain that identity. merge_commit_sha is the completed merge result only when merged=true.
- stack_state is standalone, stacked, or unknown; stack carries the observed stack data. The first-version gh.pr.merge action rejects stacked PRs and unknown scope before submission.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Discovering candidates before a pull number is known; use gh.pr.list with explicit state filters, then apply workflow-owned identity and history rules.
- Conversation history, submitted reviews, line comments, checks, or lifecycle events; use the dedicated PR sibling surfaces for those narrower views.
- Mutating or merging the pull request; this published surface is observation only.
- A test-merge candidate is not a completed merge or proof of the CI worker checkout. Missing identity stays unavailable, not invented. A snapshot gives no atomic base or stack guarantee; never replace the accepted CI head with this probe's freshly fetched head when authoring expected_head_sha.

### gh_pr_probe_step

Inspect one pull request headline snapshot before branching into narrower diff, review, comment, and checks surfaces.

```yaml
  - name: load-pr
    uses: gh.pr
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
    register: pr
```

### gh_pr_full_inspection_flow

Inspect one pull request through metadata, diff, comments, reviews, review comments, checks, and timeline surfaces, then publish a digest.

```yaml
version: 0
workflow: inspect-pr
inputs:
  repository: kergma-lw/ordo-cli # Literal ASCII OWNER/REPO, not a URL; explicit other repositories remain allowed.
  pull_number: 42
blocks:
- steps:
  - name: load-pr
    uses: gh.pr
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
    register: pr
  - name: load-pr-diff
    uses: gh.pr.diff
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_diff
  - name: load-pr-comments
    uses: gh.pr.comments
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_comments
  - name: load-pr-reviews
    uses: gh.pr.reviews
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_reviews
  - name: load-pr-review-comments
    uses: gh.pr.review_comments
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_review_comments
  - name: load-pr-checks
    uses: gh.pr.checks
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
    register: pr_checks
  - name: load-pr-timeline
    uses: gh.pr.timeline
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_timeline
  - name: publish-pr-inspection
    publish:
      summary: "Pull request inspection loaded"
      pull_ref:
        format: "{}#{}"
        args:
        - inputs.repository
        - inputs.pull_number
      title: step.pr.outputs.title
      head_sha: step.pr.outputs.head_sha
      changed_file_count: step.pr_diff.outputs.total_files
      comment_count: step.pr_comments.outputs.total_count
      review_count: step.pr_reviews.outputs.total_count
      review_comment_count: step.pr_review_comments.outputs.total_count
      check_count: step.pr_checks.outputs.total_count
      timeline_count: step.pr_timeline.outputs.total_count
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

## Effects

- None

## Failure modes

- `pull_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.pr`

```json
{
  "pull_number": 42
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
          "pull_number": 42
        },
        "reference": "gh.pr"
      }
    ],
    "failure_modes": [
      "pull_not_found",
      "probe_failed"
    ],
    "inputs": {
      "pull_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "pr",
    "outputs": {
      "additions": "integer",
      "author": "object",
      "base_ref": "string",
      "base_repository": "string",
      "base_sha": "string",
      "body": "string",
      "changed_files": "integer",
      "commits_count": "integer",
      "created_at": "string",
      "deletions": "integer",
      "draft": "boolean",
      "head_ref": "string",
      "head_repository": "string",
      "head_sha": "string",
      "merge_commit_sha": "string",
      "mergeable": "boolean",
      "mergeable_state": "string",
      "merged": "boolean",
      "merged_at": "string",
      "number": "integer",
      "repository": "string",
      "review_decision": "string",
      "stack": "object",
      "stack_state": "string",
      "state": "string",
      "test_merge_base_sha": "string",
      "test_merge_head_sha": "string",
      "test_merge_reason": "string",
      "test_merge_sha": "string",
      "test_merge_state": "string",
      "title": "string",
      "updated_at": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read normalized metadata from a GitHub pull request.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr",
  "reference": "gh.pr",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
