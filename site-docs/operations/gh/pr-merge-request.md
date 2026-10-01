# GitHub pr merge request

Observe the saved merge request for one pull request after submitting it.

Observe one saved asynchronous GitHub merge request UUID once and report its pending, merged, failed, or enqueued state.

## Use when

- Provide the pull request number and request identity saved from gh.pr.merge. Leave repository out to use the workflow's GitHub repository context, or name another repository explicitly. Provide a valid ASCII OWNER/REPO value; an invalid explicit value is rejected rather than falling back to the workflow target. The selected repository and pull number must match the saved request.
- pending means unfinished; merged reports merge_sha; enqueued means queued, not merged. A successfully observed failed state is a successful probe observation of an unsuccessful merge, with GitHub's message preserved.
- Requests are retained for 24 hours. An expired or missing request ID is unavailable evidence, not proof that the merge failed. Preserve uncertainty rather than blindly resubmitting.
- Use the request state and availability together; merged=false alone cannot distinguish pending, failed, enqueued, or unavailable evidence and is not proof of an unmerged PR. Confirm current PR completion with gh.pr when the workflow needs that fact.

## What to provide

- `pull_number`: required; provide the saved pull request number from `gh.pr.merge`. `request_id`: required; provide the saved request identity from `gh.pr.merge`. `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.

## Result and boundary

- Later steps can use `repository`, `pull_number`, `request_id`, `state`, `merged`, `merge_sha`, `merge_method`, `merge_action`, and `message`. An unavailable request leaves `merged` and `merge_sha` unknown; it is not proof that the pull request failed or remained unmerged.
- Usable result fact: `expected_head_sha`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Polling, queue administration, or a new merge submission. Use gh.pr.merge to submit after CI acceptance.
- Treating an unavailable request or a failure message as a complete explanation of the pull request state. This observation does not freeze the pull request's base or scope.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.pr.merge`](pr-merge.md): Submit with expected_head_sha from the accepted CI head and retain request_id
- [`connector.gh.pr`](pr.md): Observe current PR facts rather than the saved request lifecycle
- [`connector.gh.pr.checks`](pr-checks.md): Inspect CI attached to head H or candidate M; candidate checks bind expected H, not M

## Inspect next

- connector.gh.pr.merge
- connector.gh.pr
- connector.gh.pr.checks

## Exact machine contract

Use `ordo-help operation gh.pr.merge.request --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_async_merge_head_context

Authorize a merge explicitly, save the pull request source revision, and require the workflow's chosen checks for that saved revision before submitting a squash merge. Save the returned request ID, inspect it once when present, and then read the pull request again. Only the final pull request observation confirms whether it merged. With the workflow's GitHub repository context available, merge and request omit repository; explicit repository overrides remain supported. Pull-request reads and checks use an explicit input guarded to match that context.

```yaml
version: 0
workflow: gh-pr-merge-head-context
# Requires the GitHub repository context to be acme/mobile-app.
# Supply that context through profile YAML: connectors: {gh: {repository: acme/mobile-app}}
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
