# GitHub asynchronous pull request merge requirements

## Scope and ownership

- PR creation belongs to the separate [gh.pr.create action](gh-pr-create.md), whose exact open-duplicate refusal and uncertain POST result differ from merge-request reuse.

- `gh.pr.merge` is a mutation action submitting a direct asynchronous merge for one standalone PR. `gh.pr.merge.request` is a read-only probe observing one saved request once.
- These are the agreed target semantics. Existing implementation differences are drift to resolve, not justification for weakening the contract.
- Workflow policy owns authorization, required CI selection, trusted producer selection, freshness, and the decision to submit. Observation helpers expose evidence; the action does not synthesize approval from `mergeable`, review summaries, or a green aggregate.
- No stack support: before PUT the action must validate PR identity and observe stack scope. A valid stack object means `stacked` and fails as `unsupported_stack`; null or malformed stack data means `unknown` and fails as `merge_scope_unknown`. Only an absent API stack property on a validated ordinary PR envelope means `standalone`. A failed pre-read API call fails as `merge_api_failed`. All these failures prevent PUT.

## Submission contract

- Resolve the optional `repository` from a valid explicit `OWNER/REPO` override or, when omitted or null, from the bootstrapped `connector_contexts.gh.repository`. A malformed explicit value must fail without falling back to context; no resolved repository is an error. Context is a default, not an authorization allowlist. Require explicit positive integer `pull_number`, `merge_method: merge|squash|rebase`, and full 40-character hexadecimal `expected_head_sha`. Do not substitute a default method or a freshly observed head as the expected SHA.
- After validating inputs, stack admission, and the observed head, send one `PUT repos/{repository}/pulls/{pull_number}/merge-async` with `sha=expected_head_sha`, the explicit `merge_method`, and `merge_action=direct_merge`. A pre-read head differing from expected H is `head_mismatch` with `submission=not_submitted`; never replace H with that newer head. The server-side SHA guard remains required for changes after pre-read. Preserve HTTP status and response body even if the CLI exits nonzero.
- Do not wait, poll, automatically retry, request a merge queue, use admin bypass, or fall back to a synchronous merge. Observing an already-enqueued response does not authorize queue submission or establish merge completion.
- Repository rules are evaluated by GitHub for the authenticated actor. The connector does not request a bypass or alter rules; it cannot revoke server-configured bypass privileges already granted to that actor. Workflows and repository administrators must not mistake this action for an independent enforcement layer over GitHub permissions.
- A pending accepted request must provide a valid UUID and demonstrably matching method, direct action, and expected head. Save its `request_id`, repository, and PR number for later observation. Acceptance is not completion.
- An existing request (HTTP 409) is reusable only when those exact parameters match, with hexadecimal SHA case normalized. Different known parameters mean `existing_request_conflict`; absent or unrecognized parameters mean `existing_request_unknown`. HTTP 409 is not evidence of head mismatch.
- An already-merged response may have no UUID. Preserve a null `request_id`; do not invent one. Require an explicit merged state and valid resulting SHA to establish `merged: true`. A validated pre-read PR that is closed and explicitly merged with a valid `merge_commit_sha` may return `already_merged` before stack/head admission because no PUT is needed.
- Distinguish local admission/input failure, API failure, explicit merge refusal, and unknown mutation outcome. Any failed API pre-read is `merge_api_failed` with `submission=not_submitted`; malformed/mismatched PR identity in a 200 response is `merge_scope_unknown`. PUT 400 is `merge_refused` with `submission=refused`; PUT 403/404/422 is `merge_api_failed` with `submission=api_failed`. Ambiguous PUT results, malformed acceptance, and server/transport failures are `merge_result_unknown`, not proof that nothing happened; never blindly retry.
- Publish repository and PR identity, `request_id`, `state`, `merged`, `merge_sha`, `merge_method`, `merge_action`, `expected_head_sha`, `http_status`, `message`, plus action-specific `submission`, `request_compatibility`, `stack_scope`, and `observed_head_sha`. `submission` includes `not_submitted` and `api_failed` as well as accepted/existing/already-completed/refused/unknown states. `stack_scope` reports the action-time classification, and `observed_head_sha` reports the pre-read head once available for comparison.
- Shared `merged` is nullable: true for validated merged evidence, false for validated pending/failed/enqueued evidence, and null for unavailable/error or malformed evidence. `merge_sha` is populated only from validated merged evidence. Reported request parameters remain null when unavailable; the local `head_mismatch` diagnostic explicitly includes the caller's expected H alongside the observed H without claiming those are accepted request parameters.

## Request observation contract

- Resolve optional repository by the same explicit-override/bootstrap-context contract as the merge action, and require explicit PR number and the saved UUID `request_id`; perform one GET of the corresponding `merge-async/{request_id}` resource. The resolved repository and PR number must identify the saved request's target.
- Expose `pending`, `merged`, `enqueued`, and `failed` distinctly. Successfully observing `failed` is a successful probe outcome with a failed remote request state, not an API failure.
- Async failed-request responses have no machine-readable failure code. Preserve `message` verbatim; do not infer or invent `head_mismatch` from prose.
- Requests are retained for 24 hours. A 404, expired/inaccessible request, transport/API error, malformed response, or unrecognized state is `request_unavailable`, not evidence that the merge failed. Retain the requested handle and available HTTP/message diagnostics.

## CI identity and race boundaries

- Capture initial `gh.pr` head H, then obtain `gh.pr.checks` with `expected_head_sha=H`. Submit that same H only after workflow-owned CI/authorization/freshness admission passes. Never replace H with a newer head after evaluating old CI.
- For test-merge checks, verify synthetic M against the snapshot's ordered parents `[B, H]`, select `target=test_merge`, and still submit `expected_head_sha=H`, not M. API attachment to H or M does not prove the actual CI checkout.
- The endpoint supplies a head guard only: there is no atomic base-SHA guard. Base movement after verification can invalidate the workflow's assumptions despite unchanged H.
- Stack rejection is based on a pre-read, not an atomic server-side standalone constraint. Membership can change between observation and PUT; do not promise this race is eliminated or claim stack support because GitHub itself can merge preceding stack PRs.
- Direct merge may cause GitHub's automatic linked-issue closure and repository-configured branch deletion. The connector does not suppress these GitHub side effects or imply it explicitly issued separate issue/branch mutations.

## Runtime and discovery parity

| Mode | Required source semantics |
| --- | --- |
| `check` | Validate operation kind, inputs, references, and gate structure; never submit a merge or interpret static validity as CI authorization. |
| `review` | Expose mutation effects, preflight PR/stack facts, saved-head provenance, and unresolved policy/race constraints without submitting. |
| `plan` | Preserve ordered snapshot → pinned checks → late admission → action → explicit observation data flow; acceptance remains asynchronous. |
| `run` | Enforce the workflow gate and action's own stack admission, attempt at most one PUT, publish actual outcome and invalidate affected observations. |
| `explain` | Explain head versus test-merge/result SHA, policy ownership, refusal versus unknown outcome, retention, and stack/base race limits without mutation. |
| `next` | Respect blocked admission and unknown/pending outcomes; suggest explicit observation or policy reevaluation where appropriate, never silently retry or treat acceptance as merged. |

- Action preflight fields are `state`, `draft`, `head_sha`, and `stack_state`. A review-time preflight is not a substitute for the action's own pre-PUT stack/head checks.
- Published invalidation handles are `gh.pr.*`, `gh.issue`, and `gh.project.issue`; saved request evidence remains distinct from a fresh observation. Verify that runtime prefix invalidation covers both the root `gh.pr` and its descendant probes. Saved registered snapshots must not be mistaken for refreshed observations.
- Review affected `ordo-help features`, `overview`, `model`, `workflow-authoring`, `capabilities`, `command-line`, `operations`, `describe`, and `search` surfaces. Publish action/probe separation, required inputs, output nullability, failure meanings, unsupported stack/queue/bypass behavior, and asynchronous lifecycle consistently.
- Affected describe surfaces must satisfy the describe readiness checklist. Relevant verified snippets must cover the safe saved-H flow and request observation. If snippet-world support cannot represent the necessary gate/evidence shape, record that parity blocker rather than publishing a decorative example as verified.

## Verification criteria

Use mocked GitHub responses for connector scenarios and the bounded fixture executor for canonical workflow scenarios; verification must not merge a live PR. These are acceptance criteria, not a claim that every scenario belongs to the snippet executor:

1. Invalid/missing identity, method, SHA, or UUID fails before transport. Uppercase hexadecimal pins compare equivalently.
2. Absent stack on a validated envelope is standalone; explicit null is unknown. Stacked, malformed, indeterminate, mismatched-identity, and failed stack reads demonstrate no PUT with the appropriate unsupported/scope/API failure. A newer action-time stack read overrides an earlier standalone preflight for admission. Race coverage/documentation does not claim atomic exclusion.
3. Each explicit method sends exactly one direct async PUT with H. No polling, queue request, bypass, synchronous fallback, or hidden retry occurs.
4. Accepted pending request preserves its UUID and exact parameters. Existing exact requests are reusable; mismatched or missing parameters yield conflict/unknown. A 409 never becomes fabricated head mismatch.
5. Already merged preserves resulting SHA and null UUID where absent. Already enqueued remains not merged. Missing result SHA cannot establish merged success.
6. PUT 400 refusal and PUT 403/404/422 API failure preserve distinct outcomes and HTTP/message evidence. Pre-read API failure is not submitted. Malformed PUT responses, server/transport failures, and ambiguous acceptance preserve unknown mutation status and do not retry. Unavailable evidence has `merged=null`, not fabricated false.
7. Saved action outputs feed the request probe. Pending, merged, enqueued, and failed are successfully observed once; failed preserves the unstructured message. Expiration/404, permissions, transport failures, and malformed observations are unavailable, not failed merge proof.
8. Initial H with green checks followed by H2 blocks pinned check retrieval, yields action pre-read `head_mismatch` without PUT, or remains protected by the server's H guard if movement occurs after pre-read. Delayed failure prose never invents a structured reason. The action never upgrades H to H2. Canonical workflow fixtures verify mismatched-SHA, untrusted, missing-required, and incomplete CI admission. Timestamp-age freshness remains workflow-owned and is not implemented by the canonical snippets; a future freshness-gate example requires explicit supported policy/fixture inputs and verification.
9. Test merge M with exact parents `[B, H]` selects M checks while submission pins H. Wrong/reordered parents, missing M, or wrong attached SHA fail closed; actual checkout is never inferred. Base movement after observation remains an explicitly unguarded race.
10. Multi-page statuses/check runs include failures on later pages. Inconsistent totals, duplicate identities/contexts, missing SHA, no checks, skipped, neutral, unknown, and mixed results never become complete aggregate success.
11. Exercise all six runtime modes and affected discovery surfaces against the semantics above, including action/probe distinction and saved-handle flow. Canonical snippets `gh_pr_async_merge_head` and `gh_pr_async_merge_test_merge` verify pinned-head/CI gates, UUID handoff, and final PR observation through bounded fixture execution. Do not present their coverage as timestamp-age freshness, connector HTTP execution, atomic race protection, or live GitHub verification. See the [snippet-world model](../../model/help/snippet-worlds.md) for supported shapes and limitations.
