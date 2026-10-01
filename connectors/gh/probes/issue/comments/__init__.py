"""gh.issue.comments probe."""

from __future__ import annotations

import json

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe
from ordo.model.human import declare_human

COMMENTS_OUTPUTS = {
    "issue_ref": "string",
    "total_count": "number",
    "comments": ["object"],
}


HUMAN = declare_human({'title': 'GitHub issue comments',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and workflow logic now needs '
         'prior discussion for one issue there.',
 'summary': 'Probe the comment thread of one GitHub issue as a typed list of recent comments plus total count '
            'metadata. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit '
            'repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and workflow '
                         'logic now needs prior discussion for one issue there.',
                         'Workflow logic needs to inspect prior discussion, count comments, or publish a compact '
                         'conversation summary before taking another step.']},
              {'heading': 'Do not use for',
               'items': ["Reading the issue's main body, labels, or state; use connector.gh.issue for the broader "
                         'issue snapshot.',
                         'Posting a new comment; use connector.gh.issue.comment.add for that effectful change.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.issue',
                               'summary': 'Sibling probe for the issue snapshot rather than its comment list'},
                              {'handle': 'connector.gh.issue.comment.add',
                               'summary': 'Action for appending one new comment to the same thread'},
                              {'handle': 'connector.gh.issue.body.append',
                               'summary': 'Issue-body mutation surface when the update belongs in the issue body '
                                          'rather than the comment thread'}]},
              {'heading': 'Inspect next',
               'items': ['connector.gh.issue', 'connector.gh.issue.comment.add', 'connector.gh.issue.body.append']}]})

def info():
    return probe(
        name="issue.comments",
        human=HUMAN,
        inputs={**ISSUE_IDENTITY_INPUTS, "limit": "integer"},
        outputs=COMMENTS_OUTPUTS,
        failure_modes=("issue_not_found", "limit_invalid", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_issue_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_issue_comments")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    owner = identity.owner
    repo = identity.repo
    number = identity.issue_number
    limit = _resolve_limit(ctx, issue_ref=issue_ref)
    if isinstance(limit, OperationOutcome):
        return limit

    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                (
                    "query="
                    "query($owner:String!,$repo:String!,$number:Int!,$limit:Int!){"
                    "repository(owner:$owner,name:$repo){"
                    "issue(number:$number){"
                    "comments(first:$limit){totalCount nodes{id url body createdAt updatedAt author{login}}}"
                    "}}}"
                ),
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
                "-F",
                f"number={number}",
                "-F",
                f"limit={limit}",
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
                        code="probe.gh_issue_comments.not_found",
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
                summary="GitHub issue comments probe failed",
                raw=outcome.raw,
                diagnostic_code="probe.gh_issue_comments.command_failed",
                details={"issue_ref": issue_ref},
                message="GitHub issue comments probe failed",
            )
        return outcome

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="probe_failed",
            summary="GitHub issue comments output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue_comments.invalid_json",
                    level="error",
                    message="GitHub issue comments output was not valid JSON",
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
                    code="probe.gh_issue_comments.not_found",
                    level="error",
                    message="GitHub issue was not found",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    comments_data = issue_data.get("comments") if isinstance(issue_data, dict) else None
    if not isinstance(repository_data, dict) or not isinstance(issue_data, dict) or not isinstance(comments_data, dict):
        return fail(
            code="probe_failed",
            summary="GitHub issue comments output was not an object",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue_comments.invalid_shape",
                    level="error",
                    message="GitHub issue comments output was not an object",
                    details={"reference": ctx.reference},
                ),
            ),
            raw=command.raw,
        )

    nodes = comments_data.get("nodes")
    total_count = comments_data.get("totalCount")
    if not isinstance(nodes, list) or not isinstance(total_count, int):
        return fail(
            code="probe_failed",
            summary="GitHub issue comments output was missing required fields",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue_comments.missing_fields",
                    level="error",
                    message="GitHub issue comments output was missing required fields",
                    details={"reference": ctx.reference},
                ),
            ),
            raw=command.raw,
        )

    return ok(
        summary="GitHub issue comments retrieved successfully",
        outputs={
            "issue_ref": issue_ref,
            "total_count": total_count,
            "comments": nodes,
        },
        raw=command.raw,
    )


def _resolve_limit(ctx: OperationContext, *, issue_ref: str) -> int | OperationOutcome:
    try:
        raw = ctx.input("limit")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return 20
        return exc.outcome
    limit = _coerce_positive_int(raw)
    if limit is None:
        return fail(
            code="limit_invalid",
            summary="GitHub issue comments limit must be a positive integer",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue_comments.invalid_limit",
                    level="error",
                    message="GitHub issue comments limit must be a positive integer",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "limit": raw},
                ),
            ),
        )
    return limit


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            number = int(stripped)
            return number if number > 0 else None
    return None
