# GitHub asynchronous pull request merge model

## Public operations

PR creation is modeled separately in [gh.pr.create](gh-pr-create.md); its `already_exists` refusal is not merge-request reuse.

| Reference | Kind | Inputs |
| --- | --- | --- |
| `gh.pr.merge` | action | Optional `repository`; required positive integer `pull_number`, `merge_method` (`merge`, `squash`, `rebase`), full hexadecimal `expected_head_sha` |
| `gh.pr.merge.request` | probe | Optional `repository`; required positive integer `pull_number`, saved UUID `request_id` |

Both operations resolve repository from a valid explicit `OWNER/REPO` override or, when omitted or null, from the bootstrapped `connector_contexts.gh.repository`. Malformed explicit values fail without context fallback, and no resolved repository is an error. Context supplies a default rather than an authorization allowlist. Request observation must resolve to the saved request's repository and PR number. Canonical examples may require an explicit repository as workflow policy; that does not make the operation argument required.

The [requirements](../../requirements/connector/gh-pr-merge.md) define the agreed standalone-only contract and verification obligations. [PR observation](gh-pr.md) supplies metadata, stack classification, and pinned CI evidence. Workflow policy authorizes the action; connector normalization does not decide policy.

## Submission and observation state

The action validates inputs and PR identity, observes stack admission and head identity, and performs at most one asynchronous PUT. Only an absent API `stack` property on a validated ordinary PR envelope means `standalone`. Explicit null or malformed stack data means `unknown` and produces `merge_scope_unknown`; a valid stack object means `stacked` and produces `unsupported_stack`. Neither failure submits a merge. A failed API pre-read produces `merge_api_failed` with `submission=not_submitted`.

For an otherwise admitted PR, pre-read head H2 differing from the caller's expected H produces `head_mismatch`, preserving both expected and observed heads, with no PUT. If H changes after that comparison, the submitted `sha=H` remains the server-side guard. A validated pre-read of a closed, explicitly merged PR with a full resulting `merge_commit_sha` returns `already_merged` without stack/head admission or PUT.

The request body contains `sha=H`, the explicit method, and `merge_action=direct_merge`. The request probe performs one GET using the saved UUID. Neither operation waits or polls.

Shared output fields:

| Field | Meaning |
| --- | --- |
| `repository`, `pull_number` | Resolved target identity from repository input/context and explicit PR number |
| `request_id` | GitHub `details.uuid`, when valid; the request probe preserves its requested UUID |
| `state` | Remote status: pending, merged, enqueued, failed, or unknown/unrecognized evidence |
| `merged` | Nullable: true for validated merged evidence, false for validated pending/failed/enqueued evidence, null for unavailable/error or malformed evidence |
| `merge_sha` | Resulting SHA only from validated merged evidence (`details.sha`, or the already-merged PR pre-read); otherwise null, never substituted with H or synthetic M |
| `merge_method`, `merge_action`, `expected_head_sha` | Parameters reported in response details; unavailable values remain null. Local pre-read `head_mismatch` additionally reports the requested expected H as diagnostic evidence, not as an accepted request parameter |
| `http_status`, `message` | Preserved HTTP status and GitHub message, including failure responses |

Action-only fields:

- `submission`: `not_submitted`, `accepted`, `existing`, `already_merged`, `already_enqueued`, `refused`, `api_failed`, or `unknown`.
- `request_compatibility`: `exact`, `different`, or `unknown`, comparing reported method, action, and expected head to the requested values. SHA comparison is case-insensitive.
- `stack_scope`: action-time `standalone`, `stacked`, or `unknown`. An early already-merged return need not classify the stack and retains unknown scope.
- `observed_head_sha`: pre-read head when available for the head comparison; null on earlier exits. It must not replace the saved expected H.

| Evidence | Interpretation |
| --- | --- |
| 202, pending, valid UUID, exact parameters | Accepted; save the handle; not merged |
| 409, pending, valid UUID, exact parameters | Compatible existing request; save the handle; not a head mismatch |
| 409, different known parameters | `existing_request_conflict`; retain reported evidence |
| 409, missing/unrecognized parameters | `existing_request_unknown`; do not assume compatibility |
| 200, merged, valid resulting SHA | Already merged; `request_id` may be null |
| 200, enqueued | Already enqueued, not merged; no queue submission or bypass is implied |
| Failed API pre-read | `merge_api_failed`, `submission=not_submitted`; no PUT |
| 200 pre-read with invalid/mismatched identity or unknown scope | `merge_scope_unknown`, `submission=not_submitted`; no PUT |
| Stacked pre-read | `unsupported_stack`, `submission=not_submitted`; no PUT |
| Admitted pre-read with H2 instead of expected H | `head_mismatch`, `submission=not_submitted`; no PUT |
| PUT 400 | `merge_refused`, `submission=refused`, with HTTP/message evidence |
| PUT 403/404/422 | `merge_api_failed`, `submission=api_failed`, with HTTP/message evidence |
| Ambiguous/malformed submission or transport/server failure | `merge_result_unknown`; no automatic retry |

Input/admission rejection occurs before PUT and must remain distinguishable from GitHub refusal and unknown mutation outcome. Stack rejection must diagnose unsupported membership or unknown facts explicitly; it is not an async-request failure.

A request probe with a valid 200 response can successfully observe `state=failed`. That is remote failure evidence, whereas `request_unavailable` means the GET could not establish a supported request state. Messages are unstructured and cannot manufacture `head_mismatch`. The 24-hour retention window means 404/unavailability cannot prove that the merge failed.

## Canonical executable examples

The authored YAML source is the registered canonical snippet in `src/ordo/model/help_snippets.py`; reference these IDs rather than maintain a second YAML copy here:

| Snippet ID | Fixture world | CI target |
| --- | --- | --- |
| `gh_pr_async_merge_head` | `gh-pr-merge-head` | Head H |
| `gh_pr_async_merge_test_merge` | `gh-pr-merge-test-merge` | Synthetic M verified against H and B |

Both appear on `connector.gh.pr`, `connector.gh.pr.checks`, `connector.gh.pr.merge`, and `connector.gh.pr.merge.request`. They use the bounded `fixture_execution` path described in the [snippet-world model](../help/snippet-worlds.md). Their verification executes the exact displayed workflow with injected operation fixtures, never live GitHub.

### Authored admission and handoff

1. Require boolean `authorize_merge=true`; the authored default is false. This is explicit workflow authorization, not an inferred consequence of green CI.
2. Register initial `gh.pr` as `h`; gate on `stack_state=standalone` and a string head. Read `gh.pr.checks` with `expected_head_sha=step.h.outputs.head_sha`, registering `ci`.
3. Gate on complete source pagination, matching head/pin/target/commit evidence, `overall_state=success`, and exactly one required `unit` check from app ID 15368. That check must be a completed successful check run attached to the selected commit. This is the example's explicit required-check policy, not a connector-wide CI policy.
4. The test-merge variant additionally requires verified initial and checks candidates with matching M, H, and B. Submit with the initial H in both variants; never use M or a fresh head as the expected SHA.
5. Register the action as `submission`, publish its UUID and state, and observe `step.submission.outputs.request_id` once when present. A null UUID skips the request observation safely. Pending/failed/enqueued request states remain visible, not success-by-acceptance.
6. Read a final `gh.pr` as `final_pr` and publish confirmation from that snapshot's explicit merged fact and resulting `merge_commit_sha`. This example deliberately uses a final PR observation for confirmation; it does not redefine the request probe's valid merged evidence.

`register` is execution-local. Reusing a request in a later invocation still requires workflow-owned persistence of repository, PR number, and UUID; these examples demonstrate same-run handoff, not persistent storage or polling.

### Verified scope and limits

- Fixture scenarios exercise authorization default/type rejection, non-standalone admission, mismatched head/pin/commit evidence, missing or duplicate required checks, wrong name/app/SHA, pending/failed/skipped/unknown CI, and incomplete pagination. The test-merge variant also rejects mismatched candidate/head/base evidence.
- Request scenarios exercise UUID handoff, null-handle skipping, pending/failed/enqueued/merged state publication, and confirmation based on final PR evidence rather than request acceptance.
- Connector tests, not the snippet executor, establish raw stack/envelope validation, action-time stack/head rejection, server request construction, HTTP outcome classification, parent verification, and pagination retrieval. The fixtures supply normalized operation outcomes; they do not execute connector HTTP handlers.
- The canonical inputs are repository, PR number, and authorization. There is no timestamp-age/freshness input or gate. SHA mismatch rejection is not proof that an old successful check on unchanged H is fresh. Workflows retain responsibility for freshness and checkout attestation; a future timestamp-age example requires an explicit policy and fixture-path extension before claiming verified coverage.
- A move to H2 before action pre-read yields local `head_mismatch` without PUT; movement afterward remains guarded by server `sha=H`. These connector race boundaries are not simulated atomicity guarantees of the fixture world, and delayed failure messages do not supply a structured reason.

## Effects and limits

- Submission is asynchronous and head-guarded, without waiting, retry, queue enrollment, admin bypass, or stack support.
- GitHub applies repository rules according to the authenticated actor's permissions. No bypass is requested, but the connector cannot remove bypass privileges configured on GitHub for that actor.
- Stack pre-read is not atomic with PUT. GitHub could change membership after the read; the connector cannot promise atomic standalone-only enforcement with this endpoint.
- There is no base-SHA guard. A verified synthetic M proves a particular observed B/H pairing, not the eventual merge tree after base movement.
- CI API attachment is not proof of worker checkout. Resulting merge SHA is distinct from the observed synthetic SHA.
- GitHub may automatically close linked issues or delete branches according to repository configuration. These effects are not suppressed by direct merge. Published invalidation handles are `gh.pr.*`, `gh.issue`, and `gh.project.issue`. Runtime prefix invalidation includes the root `gh.pr` as well as its descendants; a registered earlier snapshot remains historical evidence, not a refreshed observation.
- `check`, `review`, `plan`, `explain`, and `next` must preserve this action/probe distinction without issuing PUT. `run` enforces admission and publishes actual outcomes. Full per-mode/discovery acceptance criteria are in the requirements; examples must not suggest static validation, preflight, or acceptance establishes completion.
