"""gh.issue.body.replace action."""

from __future__ import annotations

import json

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok


def info():
    return action(
        name="issue.body.replace",
        inputs={**ISSUE_IDENTITY_INPUTS, "body": "string"},
        effects=("replace GitHub issue body",),
        outputs={"issue_ref": "string", "url": "string", "body": "string", "changed": "boolean"},
        failure_modes=("issue_not_found", "body_invalid", "replace_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    body = str(ctx.input("body"))

    identity = resolve_issue_identity(ctx, failure_code="replace_blocked", diagnostic_prefix="action.gh_issue_body_replace")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    owner = identity.owner
    repo = identity.repo
    number = identity.issue_number
    issue_data = _load_issue(ctx, issue_ref=issue_ref, owner=owner, repo=repo, number=number)
    if isinstance(issue_data, OperationOutcome):
        return issue_data

    current_body = issue_data["body"]
    issue_url = issue_data["url"]
    if current_body == body:
        return ok(
            summary="GitHub issue body is already set",
            outputs={"issue_ref": issue_ref, "url": issue_url, "body": body, "changed": False},
            raw={"issue": issue_data.get("raw", {})},
        )

    try:
        command = ctx.command(
            ["gh", "issue", "edit", str(number), "-R", f"{owner}/{repo}", "--body", body],
            failures={"os_error": "replace_blocked", "nonzero": "replace_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "replace_blocked" and ("body is too long" in text or "invalid body" in text):
            return fail(
                code="body_invalid",
                summary="GitHub issue body was rejected",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_body_replace.body_invalid",
                        level="error",
                        message="GitHub issue body was rejected",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="replace_blocked",
            summary="Replacing GitHub issue body failed",
            raw=outcome.raw,
            diagnostic_code="action.gh_issue_body_replace.command_failed",
            details={"issue_ref": issue_ref},
            message="Replacing GitHub issue body failed",
        )

    return ok(
        summary="Replaced GitHub issue body",
        outputs={"issue_ref": issue_ref, "url": issue_url, "body": body, "changed": True},
        raw={"issue": issue_data.get("raw", {}), "edit": command.raw},
    )
def _load_issue(
    ctx: OperationContext, *, issue_ref: str, owner: str, repo: str, number: int
) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            ["gh", "issue", "view", str(number), "-R", f"{owner}/{repo}", "--json", "body,url"],
            failures={"os_error": "replace_blocked", "nonzero": "replace_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "replace_blocked" and text_mentions_not_found(text, "could not resolve to an issue", "issue not found"):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_body_replace.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="replace_blocked",
            summary="Inspecting GitHub issue failed",
            raw=outcome.raw,
            diagnostic_code="action.gh_issue_body_replace.issue_lookup_failed",
            details={"issue_ref": issue_ref},
            message="Inspecting GitHub issue failed",
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="replace_blocked",
            summary="GitHub issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_replace.invalid_json",
                    level="error",
                    message="GitHub issue output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(payload, dict):
        return fail(
            code="replace_blocked",
            summary="GitHub issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_replace.invalid_shape",
                    level="error",
                    message="GitHub issue output was not an object",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    body = payload.get("body")
    url = payload.get("url")
    if not isinstance(body, str) or not isinstance(url, str):
        return fail(
            code="replace_blocked",
            summary="GitHub issue output was missing required fields",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_replace.missing_fields",
                    level="error",
                    message="GitHub issue output was missing required fields",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    return {"body": body, "url": url, "raw": command.raw}
