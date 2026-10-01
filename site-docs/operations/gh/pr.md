# GitHub pr

the workflow's GitHub repository context already names the normal repository target and workflow logic now needs one PR snapshot there by pull number.

Probe one GitHub pull request as a typed metadata snapshot with head/base identity, a verified test-merge candidate, and stack scope. Prefer the workflow's GitHub repository context as the normal repository target; review warns when an explicit repository overrides it.

## Use when

- Workflow logic needs the pull request's current headline facts before deciding which narrower PR surfaces to inspect next.
- A later step needs branch refs, draft/state flags, review decision, or change totals from one normalized PR snapshot.
- head_sha and base_sha identify head H and base B with their repositories. test_merge_state=verified means candidate M has the observed parents B then H; test_merge_sha, test_merge_head_sha, and test_merge_base_sha retain that identity. merge_commit_sha is the completed merge result only when merged=true.
- stack_state is standalone, stacked, or unknown; stack carries the observed stack data. The first-version gh.pr.merge action rejects stacked PRs and unknown scope before submission.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `pull_number`: required.

## Result and boundary

- Usable result fact: `head_repository`.
- Usable result fact: `base_repository`.
- Usable result fact: `base_sha`.
- Usable result fact: `merged`.
- Usable result fact: `merged_at`.
- Usable result fact: `merge_commit_sha`.
- Usable result fact: `test_merge_sha`.
- Usable result fact: `test_merge_head_sha`.
- Usable result fact: `test_merge_base_sha`.
- Usable result fact: `test_merge_state`.
- Usable result fact: `test_merge_reason`.
- Usable result fact: `stack_state`.
- Usable result fact: `stack`.
- Usable result fact: `number`.
- Usable result fact: `repository`.
- Usable result fact: `title`.
- Usable result fact: `body`.
- Usable result fact: `author`.
- Usable result fact: `state`.
- Usable result fact: `draft`.
- Usable result fact: `url`.
- Usable result fact: `created_at`.
- Usable result fact: `updated_at`.
- Usable result fact: `base_ref`.
- Usable result fact: `head_ref`.
- Usable result fact: `head_sha`.
- Usable result fact: `mergeable`.
- Usable result fact: `mergeable_state`.
- Usable result fact: `review_decision`.
- Usable result fact: `additions`.
- Usable result fact: `deletions`.
- Usable result fact: `changed_files`.
- Usable result fact: `commits_count`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Discovering candidates before a pull number is known; use gh.pr.list with explicit state filters, then apply workflow-owned identity and history rules.
- Conversation history, submitted reviews, line comments, checks, or lifecycle events; use the dedicated PR sibling surfaces for those narrower views.
- Mutating or merging the pull request; this published surface is observation only.
- A test-merge candidate is not a completed merge. Missing identity stays unavailable, not invented. A snapshot gives no atomic base or stack guarantee; never replace the accepted CI head with this probe's freshly fetched head when authoring expected_head_sha.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.gh`: Parent GitHub connector family for issue, pull-request, and project operations
- [`connector.gh.pr.list`](pr-list.md): Discover filtered PR candidates; one item does not automatically identify the correct PR
- [`connector.gh.pr.create`](pr-create.md): Create a PR before detailed by-number inspection; existing open identity refuses creation
- [`connector.gh.pr.diff`](pr-diff.md): Sibling probe for changed files and patch content rather than PR headline metadata
- [`connector.gh.pr.reviews`](pr-reviews.md): Sibling probe for submitted review decisions rather than the PR snapshot
- [`connector.gh.pr.checks`](pr-checks.md): Observe CI attached to head H or verified candidate M
- [`connector.gh.pr.merge`](pr-merge.md): Submit a merge with expected_head_sha from accepted CI evidence
- [`connector.gh.pr.merge.request`](pr-merge-request.md): Observe completion using the saved request UUID

## Inspect next

- connector.gh.pr.diff
- connector.gh.pr.comments
- connector.gh.pr.reviews
- connector.gh.pr.checks
- connector.gh.pr.merge
- connector.gh.pr.merge.request

## Exact machine contract

Use `ordo-help operation gh.pr --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_async_merge_head

Authorize a merge explicitly, save the pull request source revision, and require the workflow's chosen checks for that saved revision before submitting a squash merge. Save the returned request ID, inspect it once when present, and then read the pull request again. Only the final pull request observation confirms whether it merged.

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
