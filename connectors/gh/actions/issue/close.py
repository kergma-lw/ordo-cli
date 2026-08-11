"""gh.issue.close action."""

from __future__ import annotations

import json

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok


def info():
    return action(
        name="issue.close",
        inputs=ISSUE_IDENTITY_INPUTS,
        effects=("close GitHub issue",),
        outputs={"issue_ref": "string", "state": "string", "closed": "boolean"},
        failure_modes=("issue_not_found", "close_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_issue_identity(ctx, failure_code="close_blocked", diagnostic_prefix="action.gh_issue_close")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    owner = identity.owner
    repo = identity.repo
    number = identity.issue_number

    inspect = _view_issue(ctx, issue_ref=issue_ref, owner=owner, repo=repo, number=number)
    if isinstance(inspect, OperationOutcome):
        return inspect

    issue_state = str(inspect.get("state") or "")
    if issue_state.upper() == "CLOSED":
        return ok(
            summary="GitHub issue is already closed",
            outputs={"issue_ref": issue_ref, "state": "CLOSED", "closed": True},
            raw={"view": inspect.get("raw", {})},
        )

    try:
        close_command = ctx.command(
            ["gh", "issue", "close", str(number), "-R", f"{owner}/{repo}"],
            failures={"os_error": "close_blocked", "nonzero": "close_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "close_blocked" and text_mentions_not_found(text, "could not resolve to an issue", "issue not found"):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_close.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="close_blocked",
            summary="Closing GitHub issue failed",
            raw=outcome.raw,
            diagnostic_code="action.gh_issue_close.command_failed",
            details={"issue_ref": issue_ref},
            message="Closing GitHub issue failed",
        )

    return ok(
        summary="Closed GitHub issue",
        outputs={"issue_ref": issue_ref, "state": "CLOSED", "closed": True},
        raw={"view": inspect.get("raw", {}), "close": close_command.raw},
    )
def _view_issue(
    ctx: OperationContext, *, issue_ref: str, owner: str, repo: str, number: int
) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            ["gh", "issue", "view", str(number), "-R", f"{owner}/{repo}", "--json", "state,url"],
            failures={"os_error": "close_blocked", "nonzero": "close_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "close_blocked" and text_mentions_not_found(text, "could not resolve to an issue", "issue not found"):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_close.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="close_blocked",
            summary="Inspecting GitHub issue state failed",
            raw=outcome.raw,
            diagnostic_code="action.gh_issue_close.inspect_failed",
            details={"issue_ref": issue_ref},
            message="Inspecting GitHub issue state failed",
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="close_blocked",
            summary="GitHub issue state output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_close.invalid_json",
                    level="error",
                    message="GitHub issue state output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(payload, dict):
        return fail(
            code="close_blocked",
            summary="GitHub issue state output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_close.invalid_shape",
                    level="error",
                    message="GitHub issue state output was not an object",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    payload["raw"] = command.raw
    return payload
