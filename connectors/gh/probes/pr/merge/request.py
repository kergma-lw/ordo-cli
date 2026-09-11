"""Observe a saved async merge request once, without polling."""

from __future__ import annotations

from connectors.gh._merge_api import MERGE_OUTPUTS, merge_api, merge_failure, request_uuid, response_outputs, valid_async_payload
from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="pr.merge.request",
        summary="Observe a saved async merge UUID once: pending, merged, enqueued, or failed. Requests expire after 24 hours; 404 is unavailable, not failure proof.",
        inputs={**PULL_IDENTITY_INPUTS, "request_id": "string"}, outputs=MERGE_OUTPUTS,
        failure_modes=("input_error", "request_unavailable"), handler=run,
        examples=({"reference": "gh.pr.merge.request", "inputs": {
            "repository": "octocat/Hello-World", "pull_number": 42,
            "request_id": "12345678-1234-1234-1234-123456789abc",
        }},),
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="input_error", diagnostic_prefix="probe.gh_pr_merge_request")
    if isinstance(identity, OperationOutcome):
        return identity
    request_id = ctx.input("request_id")
    if not request_uuid(request_id):
        return merge_failure(ctx, "input_error", "request_id must be the UUID returned by GitHub")
    response = merge_api(ctx, f"repos/{identity.repository}/pulls/{identity.pull_number}/merge-async/{request_id}")
    outputs = response_outputs(identity, response)
    outputs["request_id"] = request_id
    state = outputs["state"]
    if response.http_status == 200 and valid_async_payload(response, request_id=request_id):
        # A failed merge is a successful observation. Its unstructured message is
        # retained verbatim; it cannot reliably establish a head mismatch reason.
        return ok(summary=f"Async merge request is {state}", outputs=outputs, raw=response.raw)
    outputs.update(merged=None, merge_sha=None)
    return merge_failure(ctx, "request_unavailable", "Async merge request observation is unavailable (requests are retained for 24 hours)", outputs=outputs, raw=response.raw)
