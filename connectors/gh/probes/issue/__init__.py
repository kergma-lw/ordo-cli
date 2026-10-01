"""gh.issue package and operation."""

from __future__ import annotations

import json

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe
from ordo.model.human import declare_human

ISSUE_OUTPUTS = {
    "id": "string",
    "number": "number",
    "title": "string",
    "state": "string",
    "closed": "boolean",
    "url": "string",
    "body": "string",
    "author": "object",
    "labels": ["object"],
    "assignees": ["object"],
    "milestone": "object",
    "created_at": "string",
    "updated_at": "string",
    "closed_at": "string",
    "comments": "object",
    "reaction_groups": ["object"],
    "repository": "object",
    "state_reason": "string",
    "project_items": ["object"],
}


HUMAN = declare_human({'title': 'GitHub issue',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and workflow logic now needs one '
         'issue snapshot from that repository by issue number.',
 'summary': 'Probe one GitHub issue as a typed snapshot of its current metadata, body, labels, assignees, and '
            'project-item context. Prefer connector_contexts.gh.repository as the normal repository target and use an '
            'explicit repository argument only as a one-off override; review warns when it differs from the current gh '
            'context repository.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and workflow '
                         'logic now needs one issue snapshot from that repository by issue number.',
                         'Workflow logic needs to inspect one issue before deciding whether to comment, edit the body, '
                         'close it, or publish a summary.',
                         'A guard or later step needs typed issue facts such as state, title, labels, or body rather '
                         'than a coarse shell response.']},
              {'heading': 'Do not use for',
               'items': ["Listing the issue's comment thread only; use connector.gh.issue.comments for that narrower "
                         'conversation surface.',
                         'Mutating the issue; use connector.gh.issue.create, connector.gh.issue.comment.add, '
                         'connector.gh.issue.body.append, connector.gh.issue.body.replace, or connector.gh.issue.close '
                         'for effectful changes.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh',
                               'summary': 'Parent GitHub connector family for issue, pull request, and project '
                                          'operations'},
                              {'handle': 'connector.gh.issue.comments',
                               'summary': 'Sibling probe for the issue comment thread rather than the issue snapshot '
                                          'itself'},
                              {'handle': 'connector.gh.issue.comment.add',
                               'summary': 'Action for adding one new issue comment after inspection'},
                              {'handle': 'connector.gh.issue.close',
                               'summary': 'Action for closing the issue after inspection or cleanup'}]},
              {'heading': 'Inspect next',
               'items': ['connector.gh.issue.comments',
                         'connector.gh.issue.comment.add',
                         'connector.gh.issue.body.replace',
                         'connector.gh.issue.close']}]})

def info():
    return probe(
        name="issue",
        human=HUMAN,
        inputs=ISSUE_IDENTITY_INPUTS,
        outputs=ISSUE_OUTPUTS,
        failure_modes=("issue_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_issue_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_issue")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    owner = identity.owner
    repo = identity.repo
    number = identity.issue_number

    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                (
                    "query="
                    "query($owner:String!,$repo:String!,$number:Int!){"
                    "repository(owner:$owner,name:$repo){"
                    "nameWithOwner "
                    "issue(number:$number){"
                    "id number title state closed url body "
                    "author{login} "
                    "labels(first:100){nodes{id name color description}} "
                    "assignees(first:20){nodes{id login name}} "
                    "milestone{id title description dueOn} "
                    "createdAt updatedAt closedAt "
                    "comments{totalCount} "
                    "reactionGroups{content users{totalCount} viewerHasReacted} "
                    "stateReason "
                    "projectItems(first:50){nodes{id}}"
                    "}}}"
                ),
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
                "-F",
                f"number={number}",
            ],
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "execution_error" and text_mentions_not_found(text, "could not resolve to an issue", "issue not found"):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="probe.gh_issue.not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        if outcome.status == "execution_error":
            return fail_github_command(
                ctx,
                code="probe_failed",
                summary="GitHub issue probe failed",
                raw=outcome.raw,
                diagnostic_code="probe.gh_issue.command_failed",
                details={"issue_ref": issue_ref},
                message="GitHub issue probe failed",
            )
        return outcome

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="probe_failed",
            summary="GitHub issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue.invalid_json",
                    level="error",
                    message="GitHub issue output was not valid JSON",
                    details={"reference": ctx.reference, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    repository_data = ((payload.get("data") or {}).get("repository"))
    issue_data = ((repository_data or {}).get("issue"))
    if issue_data is None:
        return fail(
            code="issue_not_found",
            summary="GitHub issue was not found",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue.not_found",
                    level="error",
                    message="GitHub issue was not found",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(repository_data, dict) or not isinstance(issue_data, dict):
        return fail(
            code="probe_failed",
            summary="GitHub issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue.invalid_shape",
                    level="error",
                    message="GitHub issue output was not an object",
                    details={"reference": ctx.reference},
                ),
            ),
            raw=command.raw,
        )

    return ok(
        summary="GitHub issue retrieved successfully",
        outputs=_to_public_outputs(repository_data, issue_data),
        raw=command.raw,
    )
def _nodes(value: object) -> list[object]:
    nodes = ((value or {}).get("nodes")) if isinstance(value, dict) else None
    return nodes if isinstance(nodes, list) else []


def _to_public_outputs(repository_data: dict[str, object], issue_data: dict[str, object]) -> dict[str, object]:
    return {
        "id": issue_data.get("id"),
        "number": issue_data.get("number"),
        "title": issue_data.get("title"),
        "state": issue_data.get("state"),
        "closed": issue_data.get("closed"),
        "url": issue_data.get("url"),
        "body": issue_data.get("body"),
        "author": issue_data.get("author"),
        "labels": _nodes(issue_data.get("labels")),
        "assignees": _nodes(issue_data.get("assignees")),
        "milestone": issue_data.get("milestone"),
        "created_at": issue_data.get("createdAt"),
        "updated_at": issue_data.get("updatedAt"),
        "closed_at": issue_data.get("closedAt"),
        "comments": issue_data.get("comments"),
        "reaction_groups": issue_data.get("reactionGroups"),
        "repository": {"nameWithOwner": repository_data.get("nameWithOwner")},
        "state_reason": issue_data.get("stateReason"),
        "project_items": _nodes(issue_data.get("projectItems")),
    }
