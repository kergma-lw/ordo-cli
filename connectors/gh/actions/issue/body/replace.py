"""gh.issue.body.replace action."""

from __future__ import annotations

import json
import re

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok

_ISSUE_REF_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<repo>[^#]+)#(?P<number>\d+)$")


def info():
    return action(
        name="issue.body.replace",
        inputs={"issue_ref": "string", "body": "string"},
        effects=("replace GitHub issue body",),
        outputs={"issue_ref": "string", "url": "string", "body": "string", "changed": "boolean"},
        failure_modes=("issue_not_found", "body_invalid", "replace_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    issue_ref = str(ctx.input("issue_ref"))
    body = str(ctx.input("body"))

    parsed = _parse_issue_ref(issue_ref)
    if parsed is None:
        return fail(
            code="replace_blocked",
            summary="GitHub issue reference must use OWNER/REPO#N format",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_replace.invalid_issue_ref",
                    level="error",
                    message="GitHub issue reference must use OWNER/REPO#N format",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
        )

    owner, repo, number = parsed
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
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
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
        return fail(
            code="replace_blocked",
            summary="Replacing GitHub issue body failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_replace.command_failed",
                    level="error",
                    message="Replacing GitHub issue body failed",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=outcome.raw,
        )

    return ok(
        summary="Replaced GitHub issue body",
        outputs={"issue_ref": issue_ref, "url": issue_url, "body": body, "changed": True},
        raw={"issue": issue_data.get("raw", {}), "edit": command.raw},
    )


def _parse_issue_ref(value: str) -> tuple[str, str, int] | None:
    match = _ISSUE_REF_RE.match(value)
    if match is None:
        return None
    return match.group("owner"), match.group("repo"), int(match.group("number"))


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
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if outcome.status == "replace_blocked" and (
            "could not resolve to an issue" in text or "issue not found" in text or "not found" in text
        ):
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
        return fail(
            code="replace_blocked",
            summary="Inspecting GitHub issue failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_replace.issue_lookup_failed",
                    level="error",
                    message="Inspecting GitHub issue failed",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=outcome.raw,
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
