# GitHub pr merge

Request a merge for one accepted pull request while preserving the exact source revision that checks accepted.

Submit one asynchronous GitHub merge request for a standalone pull request, bound to the source revision accepted by the workflow.

## Use when

- Provide the pull request number, merge method (merge, squash, or rebase), and expected_head_sha. Use the workflow's GitHub repository context normally, or name another repository explicitly when needed.
- expected_head_sha is the full 40-character commit ID of the pull request source revision whose checks the workflow accepted. Take it from gh.pr.head_sha or gh.pr.checks.head_sha at that decision point, save it, and pass the saved value unchanged. Do not replace it with a later read.
- The pull request must be a standalone pull request with a known scope. The action does not submit a merge when that cannot be established or when its current head differs from expected_head_sha.
- Save request_id with the repository and pull request number for gh.pr.merge.request. Later decisions can use submission, state, merged, merge_sha, observed_head_sha, stack_scope, and request_id. A submitted or queued request is not proof of completion.
- A result can confirm that the request was submitted, that the pull request was already merged or queued, or that GitHub refused it. An unknown result confirms none of these outcomes: inspect the saved request and the pull request before deciding whether to try again.

## What to provide

- `pull_number`: required. `merge_method`: required and is `merge`, `squash`, or `rebase`. `expected_head_sha`: required and is the accepted pull request head as a full 40-character commit ID.
- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call. Retain the accepted head before this action; do not substitute a newer observation.

## Result and boundary

- Later steps can use `repository`, `pull_number`, `request_id`, `state`, `merged`, `merge_sha`, `merge_method`, `merge_action`, `expected_head_sha`, `message`, `submission`, `request_compatibility`, `stack_scope`, and `observed_head_sha`. `request_id` with the repository and pull number identifies the submitted request for `gh.pr.merge.request`.
- `submission=accepted` or `existing` confirms a compatible request, not completion. `already_enqueued` is not merged. An unknown result is not proof of submission or non-submission. Head mismatch, unsupported or unknown stack scope, and failed preflight reading submit no merge.
- The source revision guard does not lock the target branch or stack membership; concurrent changes require a new workflow decision.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails. Required preflight facts must be established before the change is submitted.

## Do not use for

- No atomic base or stack guarantee is provided: the source revision guard does not freeze the target branch or prevent a later stack change. Stacked and unknown scope are rejected.
- Waiting for completion, managing a queue, changing merge settings, or deleting branches.
- Treating submission as completion. Use gh.pr.merge.request to observe the saved request, and gh.pr when the workflow needs the pull request's current state.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.pr`](pr.md): Observe PR identity and stack scope
- [`connector.gh.pr.checks`](pr-checks.md): Observe CI evidence whose accepted head must be retained
- [`connector.gh.pr.merge.request`](pr-merge-request.md): Observe the saved request UUID once after submission

## Inspect next

- connector.gh.pr.checks
- connector.gh.pr
- connector.gh.pr.merge.request

## Exact machine contract

Use `ordo-help operation gh.pr.merge --json` when you need the exact machine-readable input and result contract for this operation.

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
