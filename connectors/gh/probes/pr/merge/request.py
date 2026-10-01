"""Observe a saved async merge request once, without polling."""

from __future__ import annotations

from connectors.gh._merge_api import MERGE_OUTPUTS, merge_api, merge_failure, request_uuid, response_outputs, valid_async_payload
from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub pr merge request',
  'goal': 'Observe the saved merge request for one pull request after submitting it.',
 'summary': 'Observe one saved asynchronous GitHub merge request UUID once and report its pending, merged, failed, or '
            'enqueued state.',
 'sections': [{'heading': 'Use when',
               'items': ['Provide the pull request number and request identity saved from gh.pr.merge. Leave repository out to use the workflow\'s GitHub repository context, or name another repository explicitly. Provide a valid ASCII OWNER/REPO value; an invalid explicit value is rejected rather than falling back to the workflow target. The selected repository and pull number must match the saved request.',
                         'pending means unfinished; merged reports merge_sha; enqueued means queued, not merged. A '
                         'successfully observed failed state is a successful probe observation of an unsuccessful '
                         "merge, with GitHub's message preserved.",
                          'Requests are retained for 24 hours. An expired or missing request ID is unavailable evidence, '
                          'not proof that the merge failed. Preserve uncertainty '
                         'rather than blindly resubmitting.',
                         'Use the request state and availability together; merged=false alone cannot distinguish '
                         'pending, failed, enqueued, or unavailable evidence and is not proof of an unmerged PR. '
                         'Confirm current PR completion with gh.pr when the workflow needs that fact.']},
                {'heading': 'What to provide',
                  'items': ['`pull_number`: required; provide the saved pull request number from `gh.pr.merge`. `request_id`: required; provide the saved request identity from `gh.pr.merge`. `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow\'s playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.']},
               {'heading': 'Result and boundary',
                'items': ['Later steps can use `repository`, `pull_number`, `request_id`, `state`, `merged`, `merge_sha`, `merge_method`, `merge_action`, and `message`. An unavailable request leaves `merged` and `merge_sha` unknown; it is not proof that the pull request failed or remained unmerged.']},
               {'heading': 'Do not use for',
               'items': ['Polling, queue administration, or a new merge submission. Use gh.pr.merge to submit after CI acceptance.',
                          'Treating an unavailable request or a failure message as a complete explanation of the pull request state. This observation does not freeze the pull request\'s base or scope.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.pr.merge',
                               'summary': 'Submit with expected_head_sha from the accepted CI head and retain '
                                          'request_id'},
                              {'handle': 'connector.gh.pr',
                               'summary': 'Observe current PR facts rather than the saved request lifecycle'},
                              {'handle': 'connector.gh.pr.checks',
                               'summary': 'Inspect CI attached to head H or candidate M; candidate checks bind '
                                          'expected H, not M'}]},
              {'heading': 'Inspect next',
               'items': ['connector.gh.pr.merge', 'connector.gh.pr', 'connector.gh.pr.checks']}]})

def info():
    return probe(
        name="pr.merge.request",
        human=HUMAN,
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
