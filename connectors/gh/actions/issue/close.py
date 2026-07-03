"""gh.issue.close action."""

from __future__ import annotations

import json
import re

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok

_ISSUE_REF_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<repo>[^#]+)#(?P<number>\d+)$")


def info():
    return action(
        name="issue.close",
        inputs={"issue": "string"},
        effects=("close GitHub issue",),
        outputs={"issue": "string", "state": "string", "closed": "boolean"},
        failure_modes=("issue_not_found", "close_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    issue_ref = str(ctx.input("issue"))
    parsed = _parse_issue_ref(issue_ref)
    if parsed is None:
        return fail(
            code="close_blocked",
            summary="GitHub issue reference must use OWNER/REPO#N format",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_close.invalid_issue_ref",
                    level="error",
                    message="GitHub issue reference must use OWNER/REPO#N format",
                    details={"reference": ctx.reference, "issue": issue_ref},
                ),
            ),
        )

    owner, repo, number = parsed

    inspect = _view_issue(ctx, issue_ref=issue_ref, owner=owner, repo=repo, number=number)
    if isinstance(inspect, OperationOutcome):
        return inspect

    issue_state = str(inspect.get("state") or "")
    if issue_state.upper() == "CLOSED":
        return ok(
            summary="GitHub issue is already closed",
            outputs={"issue": issue_ref, "state": "CLOSED", "closed": True},
            raw={"view": inspect.get("raw", {})},
        )

    try:
        close_command = ctx.command(
            ["gh", "issue", "close", str(number), "-R", f"{owner}/{repo}"],
            failures={"os_error": "close_blocked", "nonzero": "close_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if outcome.status == "close_blocked" and (
            "could not resolve to an issue" in text or "issue not found" in text or "not found" in text
        ):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_close.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail(
            code="close_blocked",
            summary="Closing GitHub issue failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_close.command_failed",
                    level="error",
                    message="Closing GitHub issue failed",
                    details={"reference": ctx.reference, "issue": issue_ref},
                ),
            ),
            raw=outcome.raw,
        )

    return ok(
        summary="Closed GitHub issue",
        outputs={"issue": issue_ref, "state": "CLOSED", "closed": True},
        raw={"view": inspect.get("raw", {}), "close": close_command.raw},
    )


def _parse_issue_ref(value: str) -> tuple[str, str, int] | None:
    match = _ISSUE_REF_RE.match(value)
    if match is None:
        return None
    return match.group("owner"), match.group("repo"), int(match.group("number"))


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
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if outcome.status == "close_blocked" and (
            "could not resolve to an issue" in text or "issue not found" in text or "not found" in text
        ):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_close.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail(
            code="close_blocked",
            summary="Inspecting GitHub issue state failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_close.inspect_failed",
                    level="error",
                    message="Inspecting GitHub issue state failed",
                    details={"reference": ctx.reference, "issue": issue_ref},
                ),
            ),
            raw=outcome.raw,
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
                    details={"reference": ctx.reference, "issue": issue_ref, "error": str(exc)},
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
                    details={"reference": ctx.reference, "issue": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    payload["raw"] = command.raw
    return payload
