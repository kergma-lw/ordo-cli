"""Submit one SHA-guarded direct asynchronous merge request for an ordinary PR.

The preliminary PR read is not atomic against stack membership or base changes.
Only the head SHA is guarded server-side; no expected-base guard is offered.
Async failure messages have no guaranteed structured reason codes.
"""

from __future__ import annotations

from connectors.gh._merge_api import MERGE_OUTPUTS, full_sha, merge_api, merge_failure, response_outputs, valid_async_payload
from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh._pr_stack import normalize_pr_stack, valid_pr_identity
from connectors.gh._pr_commit_evidence import observe_pr_commit
from ordo.plugin_sdk import OperationContext, OperationOutcome, action, ok, preflight_observation
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub pr merge',
  'goal': 'Request a merge for one accepted pull request while preserving the exact source revision that checks accepted.',
  'summary': 'Submit one asynchronous GitHub merge request for a standalone pull request, bound to the source revision accepted by the workflow.',
  'sections': [{'heading': 'Use when',
                'items': ['Provide the pull request number, merge method (merge, squash, or rebase), and expected_head_sha. Use the workflow\'s GitHub repository context normally, or name another repository explicitly when needed.',
                           'expected_head_sha is the full 40-character commit ID of the pull request source revision whose checks the workflow accepted. Take it from gh.pr.head_sha or gh.pr.checks.head_sha at that decision point, save it, and pass the saved value unchanged. Do not replace it with a later read.',
                           'The pull request must be a standalone pull request with a known scope. The action does not submit a merge when that cannot be established or when its current head differs from expected_head_sha.',
                           'Save request_id with the repository and pull request number for gh.pr.merge.request. Later decisions can use submission, state, merged, merge_sha, observed_head_sha, stack_scope, and request_id. A submitted or queued request is not proof of completion.',
                           'A result can confirm that the request was submitted, that the pull request was already merged or queued, or that GitHub refused it. An unknown result confirms none of these outcomes: inspect the saved request and the pull request before deciding whether to try again.']},
               {'heading': 'What to provide',
                 'items': ['`pull_number`: required. `merge_method`: required and is `merge`, `squash`, or `rebase`. `expected_head_sha`: required and is the accepted pull request head as a full 40-character commit ID.',
                            '`repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow\'s playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call. Retain the accepted head before this action; do not substitute a newer observation.']},
               {'heading': 'Result and boundary',
                'items': ['Later steps can use `repository`, `pull_number`, `request_id`, `state`, `merged`, `merge_sha`, `merge_method`, `merge_action`, `expected_head_sha`, `message`, `submission`, `request_compatibility`, `stack_scope`, and `observed_head_sha`. `request_id` with the repository and pull number identifies the submitted request for `gh.pr.merge.request`.',
                          '`submission=accepted` or `existing` confirms a compatible request, not completion. `already_enqueued` is not merged. An unknown result is not proof of submission or non-submission. Head mismatch, unsupported or unknown stack scope, and failed preflight reading submit no merge.',
                          'The source revision guard does not lock the target branch or stack membership; concurrent changes require a new workflow decision.']},
                 {'heading': 'Do not use for',
                'items': ['No atomic base or stack guarantee is provided: the source revision guard does not freeze the target branch or prevent a later stack change. Stacked and unknown scope are rejected.',
                          'Waiting for completion, managing a queue, changing merge settings, or deleting branches.',
                          'Treating submission as completion. Use gh.pr.merge.request to observe the saved request, and gh.pr when the workflow needs the pull request\'s current state.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.pr', 'summary': 'Observe PR identity and stack scope'},
                              {'handle': 'connector.gh.pr.checks',
                               'summary': 'Observe CI evidence whose accepted head must be retained'},
                              {'handle': 'connector.gh.pr.merge.request',
                               'summary': 'Observe the saved request UUID once after submission'}]},
              {'heading': 'Inspect next',
               'items': ['connector.gh.pr.checks', 'connector.gh.pr', 'connector.gh.pr.merge.request']}]})

def info():
    return action(
        name="pr.merge",
        human=HUMAN,
        summary="Request a SHA-guarded direct async merge; save request_id for gh.pr.merge.request. Acceptance is not completion.",
        inputs={**PULL_IDENTITY_INPUTS, "merge_method": "string", "expected_head_sha": "string"},
        outputs={**MERGE_OUTPUTS, "submission": "string", "request_compatibility": "string", "stack_scope": "string", "observed_head_sha": "string"},
        effects=("submit a direct asynchronous GitHub merge after observing a standalone PR; stack/base observation is not atomic",),
        failure_modes=("input_error", "unsupported_stack", "merge_scope_unknown", "head_mismatch", "merge_api_failed", "merge_refused", "existing_request_conflict", "existing_request_unknown", "merge_result_unknown"),
        invalidates_observations=("gh.pr.*", "gh.issue", "gh.project.issue"),
        preflight_observations=(preflight_observation(
            probe="gh.pr", with_={"repository": "{repository}", "pull_number": "{pull_number}"},
            fields=("state", "draft", "head_sha", "stack_state"),
        ),),
        examples=({"reference": "gh.pr.merge", "inputs": {
            "repository": "octocat/Hello-World", "pull_number": 42, "merge_method": "squash",
            "expected_head_sha": "6358cd125586d9def8c3e5943f23506202da81cc",
        }},),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="input_error", diagnostic_prefix="action.gh_pr_merge")
    if isinstance(identity, OperationOutcome):
        return identity
    method, sha = ctx.input("merge_method"), ctx.input("expected_head_sha")
    if not isinstance(method, str) or method not in ("merge", "squash", "rebase") or not full_sha(sha):
        return merge_failure(ctx, "input_error", "merge_method must be merge, squash, or rebase and expected_head_sha must be a full 40-digit hexadecimal SHA")
    before = merge_api(ctx, f"repos/{identity.repository}/pulls/{identity.pull_number}")
    preliminary = response_outputs(identity, before)
    preliminary.update(submission="not_submitted", request_compatibility="unknown", stack_scope="unknown", observed_head_sha=None)
    if before.http_status != 200:
        return merge_failure(ctx, "merge_api_failed", "Reading PR scope failed; no merge was submitted", outputs=preliminary, raw=before.raw)
    payload = before.payload
    if not valid_pr_identity(payload, repository=identity.repository, pull_number=identity.pull_number):
        return merge_failure(ctx, "merge_scope_unknown", "PR response identity is missing or does not match the requested PR", outputs=preliminary, raw=before.raw)
    # Already-merged is safe to report without interpreting stack membership or
    # comparing the requested head: this path never submits a mutation.
    if payload.get("merged") is True:
        evidence = observe_pr_commit(ctx, identity=identity, payload=payload)
        raw = {**before.raw, "merge_commit": {"state": evidence.state, "reason": evidence.reason, "graphql": evidence.raw}}
        if evidence.sha is None:
            if evidence.reason == "api_unavailable":
                return merge_failure(ctx, "merge_api_failed", "Reading completed merge commit evidence failed; no merge was submitted", outputs=preliminary, raw=raw)
            return merge_failure(ctx, "merge_scope_unknown", "Completed merge commit evidence is unavailable or does not match the PR snapshot; no merge was submitted", outputs=preliminary, raw=raw)
        preliminary.update(submission="already_merged", state="merged", merged=True, merge_sha=evidence.sha)
        return ok(summary="Pull request is already merged", outputs=preliminary, raw=raw)
    scope = normalize_pr_stack(payload)
    preliminary["stack_scope"] = scope
    if scope == "stacked":
        return merge_failure(ctx, "unsupported_stack", "Stacked pull requests are unsupported; no merge was submitted", outputs=preliminary, raw=before.raw)
    if scope == "unknown" or payload.get("merged") is not False:
        return merge_failure(ctx, "merge_scope_unknown", "PR merge scope is unavailable or malformed; no merge was submitted", outputs=preliminary, raw=before.raw)
    preliminary["observed_head_sha"] = payload["head"]["sha"]
    if payload["head"]["sha"].lower() != sha.lower():
        preliminary["expected_head_sha"] = sha
        return merge_failure(ctx, "head_mismatch", "Observed PR head differs from expected_head_sha; no merge was submitted", outputs=preliminary, raw=before.raw)
    response = merge_api(ctx, f"repos/{identity.repository}/pulls/{identity.pull_number}/merge-async",
                         fields={"sha": sha, "merge_method": method, "merge_action": "direct_merge"})
    outputs = response_outputs(identity, response)
    outputs.update(submission="unknown", request_compatibility="unknown", stack_scope=scope, observed_head_sha=payload["head"]["sha"])
    response.raw["pre_read"] = before.raw
    state, status = outputs["state"], response.http_status
    if status in (202, 409):
        expected = {"merge_method": method, "merge_action": "direct_merge", "expected_head_sha": sha.lower()}
        actual = {key: response.details.get(key) for key in expected}
        if full_sha(actual["expected_head_sha"]):
            actual["expected_head_sha"] = actual["expected_head_sha"].lower()
        known = (actual["merge_method"] in ("default", "merge", "squash", "rebase")
                 and actual["merge_action"] in ("default", "direct_merge", "merge_queue")
                 and full_sha(actual["expected_head_sha"]))
        compatibility = "exact" if actual == expected else ("different" if known else "unknown")
        outputs.update(submission="accepted" if status == 202 else "existing", request_compatibility=compatibility)
        if status == 409 and compatibility != "exact":
            code = "existing_request_conflict" if compatibility == "different" else "existing_request_unknown"
            return merge_failure(ctx, code, "Existing async merge request parameters do not demonstrably match the requested parameters", outputs=outputs, raw=response.raw)
        if state == "pending" and valid_async_payload(response) and compatibility == "exact":
            return ok(summary="Async merge request accepted" if status == 202 else "Compatible async merge request already exists",
                      outputs=outputs, raw=response.raw)
    elif status == 200 and state in ("enqueued", "merged") and valid_async_payload(response):
        outputs["submission"] = "already_merged" if state == "merged" else "already_enqueued"
        return ok(summary="Pull request is already merged" if state == "merged" else "Pull request is already enqueued (not merged)", outputs=outputs, raw=response.raw)
    elif status == 400:
        outputs["submission"] = "refused"
        return merge_failure(ctx, "merge_refused", "GitHub refused the async merge request", outputs=outputs, raw=response.raw)
    elif status in (403, 404, 422):
        outputs["submission"] = "api_failed"
        return merge_failure(ctx, "merge_api_failed", "GitHub async merge API request failed", outputs=outputs, raw=response.raw)
    outputs.update(merged=None, merge_sha=None)
    return merge_failure(ctx, "merge_result_unknown", "Async merge submission result is unknown; do not blindly retry", outputs=outputs, raw=response.raw)
