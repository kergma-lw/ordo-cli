"""gh.issue package and operation."""

from __future__ import annotations

import json

from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe

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


def info():
    return probe(
        name="issue",
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
        stderr = str(outcome.raw.get("stderr", "")).lower()
        stdout = str(outcome.raw.get("stdout", "")).lower()
        text = f"{stderr}\n{stdout}"
        if outcome.status == "execution_error" and (
            "could not resolve to an issue" in text or "issue not found" in text or "not found" in text
        ):
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
            return fail(
                code="probe_failed",
                summary="GitHub issue probe failed",
                diagnostics=(
                    Diagnostic(
                        code="probe.gh_issue.command_failed",
                        level="error",
                        message="GitHub issue probe failed",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
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
