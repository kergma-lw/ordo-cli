"""Submit one SHA-guarded direct asynchronous merge request for an ordinary PR.

The preliminary PR read is not atomic against stack membership or base changes.
Only the head SHA is guarded server-side; no expected-base guard is offered.
Async failure messages have no guaranteed structured reason codes.
"""

from __future__ import annotations

from connectors.gh._merge_api import MERGE_OUTPUTS, full_sha, merge_api, merge_failure, response_outputs, valid_async_payload
from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh._pr_stack import normalize_pr_stack, valid_pr_identity
from ordo.plugin_sdk import OperationContext, OperationOutcome, action, ok, preflight_observation


def info():
    return action(
        name="pr.merge",
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
    if payload.get("merged") is True and payload.get("state") == "closed" and full_sha(payload.get("merge_commit_sha")):
        preliminary.update(submission="already_merged", state="merged", merged=True, merge_sha=payload["merge_commit_sha"])
        return ok(summary="Pull request is already merged", outputs=preliminary, raw=before.raw)
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
