"""gh.issue.comment.add action."""

from __future__ import annotations

import json

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok


def info():
    return action(
        name="issue.comment.add",
        inputs={**ISSUE_IDENTITY_INPUTS, "body": "string"},
        effects=("add GitHub issue comment",),
        outputs={"issue_ref": "string", "comment_id": "string", "url": "string", "body": "string"},
        failure_modes=("issue_not_found", "body_invalid", "comment_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    body = str(ctx.input("body"))

    identity = resolve_issue_identity(ctx, failure_code="comment_blocked", diagnostic_prefix="action.gh_issue_comment_add")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    owner = identity.owner
    repo = identity.repo
    number = identity.issue_number

    if not body.strip():
        return fail(
            code="body_invalid",
            summary="GitHub issue comment body must not be empty",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_comment_add.body_invalid",
                    level="error",
                    message="GitHub issue comment body must not be empty",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
        )
    issue_lookup = _lookup_issue(ctx, issue_ref=issue_ref, owner=owner, repo=repo, number=number)
    if isinstance(issue_lookup, OperationOutcome):
        return issue_lookup

    try:
        command = ctx.command(
            ["gh", "issue", "comment", str(number), "-R", f"{owner}/{repo}", "--body", body],
            failures={"os_error": "comment_blocked", "nonzero": "comment_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "comment_blocked" and ("body cannot be blank" in text or "body is required" in text):
            return fail(
                code="body_invalid",
                summary="GitHub issue comment body was rejected",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_comment_add.body_invalid",
                        level="error",
                        message="GitHub issue comment body was rejected",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="comment_blocked",
            summary="Adding GitHub issue comment failed",
            raw=outcome.raw,
            diagnostic_code="action.gh_issue_comment_add.command_failed",
            details={"issue_ref": issue_ref},
            message="Adding GitHub issue comment failed",
        )

    comment_data = _lookup_latest_comment(ctx, issue_ref=issue_ref, owner=owner, repo=repo, number=number)
    if isinstance(comment_data, OperationOutcome):
        return comment_data

    return ok(
        summary="Added GitHub issue comment",
        outputs={
            "issue_ref": issue_ref,
            "comment_id": comment_data["comment_id"],
            "url": comment_data["url"],
            "body": comment_data["body"],
        },
        raw={"issue": issue_lookup.get("raw", {}), "comment": command.raw, "comment_lookup": comment_data.get("raw", {})},
    )
def _lookup_issue(
    ctx: OperationContext, *, issue_ref: str, owner: str, repo: str, number: int
) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            ["gh", "issue", "view", str(number), "-R", f"{owner}/{repo}", "--json", "id,url"],
            failures={"os_error": "comment_blocked", "nonzero": "comment_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "comment_blocked" and text_mentions_not_found(text, "could not resolve to an issue", "issue not found"):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_comment_add.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="comment_blocked",
            summary="Inspecting GitHub issue failed",
            raw=outcome.raw,
            diagnostic_code="action.gh_issue_comment_add.issue_lookup_failed",
            details={"issue_ref": issue_ref},
            message="Inspecting GitHub issue failed",
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="comment_blocked",
            summary="GitHub issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_comment_add.issue_invalid_json",
                    level="error",
                    message="GitHub issue output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(payload, dict):
        return fail(
            code="comment_blocked",
            summary="GitHub issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_comment_add.issue_invalid_shape",
                    level="error",
                    message="GitHub issue output was not an object",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )
    return {"raw": command.raw, "issue": payload}


def _lookup_latest_comment(
    ctx: OperationContext, *, issue_ref: str, owner: str, repo: str, number: int
) -> dict[str, object] | OperationOutcome:
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
                    "repository(owner:$owner,name:$repo){issue(number:$number){comments(last:1){nodes{id url body}}}}}"
                ),
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
                "-F",
                f"number={number}",
            ],
            failures={"os_error": "comment_blocked", "nonzero": "comment_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail_github_command(
            ctx,
            code="comment_blocked",
            summary="Inspecting latest GitHub issue comment failed",
            raw=exc.outcome.raw,
            diagnostic_code="action.gh_issue_comment_add.comment_lookup_failed",
            details={"issue_ref": issue_ref},
            message="Inspecting latest GitHub issue comment failed",
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="comment_blocked",
            summary="GitHub comment output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_comment_add.comment_invalid_json",
                    level="error",
                    message="GitHub comment output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    issue = (((payload.get("data") or {}).get("repository") or {}).get("issue"))
    comments = (((issue or {}).get("comments") or {}).get("nodes")) if isinstance(issue, dict) else None
    if not isinstance(comments, list) or not comments:
        return fail(
            code="comment_blocked",
            summary="GitHub comment output did not include the new comment",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_comment_add.comment_missing",
                    level="error",
                    message="GitHub comment output did not include the new comment",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    comment = comments[-1]
    if not isinstance(comment, dict):
        return fail(
            code="comment_blocked",
            summary="GitHub comment output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_comment_add.comment_invalid_shape",
                    level="error",
                    message="GitHub comment output was not an object",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    comment_id = comment.get("id")
    url = comment.get("url")
    body = comment.get("body")
    if not isinstance(comment_id, str) or not isinstance(url, str) or not isinstance(body, str):
        return fail(
            code="comment_blocked",
            summary="GitHub comment output was missing required fields",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_comment_add.comment_missing_fields",
                    level="error",
                    message="GitHub comment output was missing required fields",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    return {"comment_id": comment_id, "url": url, "body": body, "raw": command.raw}
