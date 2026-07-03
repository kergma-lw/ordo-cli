"""gh.issue.body.append action."""

from __future__ import annotations

import json
import re

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok

_ISSUE_REF_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<repo>[^#]+)#(?P<number>\d+)$")
_DEFAULT_SEPARATOR = "\n\n"


def info():
    return action(
        name="issue.body.append",
        inputs={"issue_ref": "string", "text": "string", "separator": "string | null"},
        effects=("append text to GitHub issue body",),
        outputs={"issue_ref": "string", "url": "string", "body": "string", "changed": "boolean"},
        failure_modes=("issue_not_found", "text_invalid", "append_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    issue_ref = str(ctx.input("issue_ref"))
    text = str(ctx.input("text"))
    separator = _optional_separator(ctx)
    if isinstance(separator, OperationOutcome):
        return separator

    parsed = _parse_issue_ref(issue_ref)
    if parsed is None:
        return fail(
            code="append_blocked",
            summary="GitHub issue reference must use OWNER/REPO#N format",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.invalid_issue_ref",
                    level="error",
                    message="GitHub issue reference must use OWNER/REPO#N format",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
        )

    if not text.strip():
        return fail(
            code="text_invalid",
            summary="GitHub issue append text must not be empty",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.text_invalid",
                    level="error",
                    message="GitHub issue append text must not be empty",
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
    effective_separator = separator if separator is not None else _DEFAULT_SEPARATOR
    if current_body:
        new_body = current_body + effective_separator + text
    else:
        new_body = text

    try:
        command = ctx.command(
            ["gh", "issue", "edit", str(number), "-R", f"{owner}/{repo}", "--body", new_body],
            failures={"os_error": "append_blocked", "nonzero": "append_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text_blob = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if outcome.status == "append_blocked" and ("body is too long" in text_blob or "invalid body" in text_blob):
            return fail(
                code="text_invalid",
                summary="GitHub issue append text was rejected",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_body_append.text_invalid",
                        level="error",
                        message="GitHub issue append text was rejected",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail(
            code="append_blocked",
            summary="Appending to GitHub issue body failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.command_failed",
                    level="error",
                    message="Appending to GitHub issue body failed",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=outcome.raw,
        )

    return ok(
        summary="Appended text to GitHub issue body",
        outputs={"issue_ref": issue_ref, "url": issue_url, "body": new_body, "changed": True},
        raw={"issue": issue_data.get("raw", {}), "edit": command.raw},
    )


def _optional_separator(ctx: OperationContext) -> str | None | OperationOutcome:
    try:
        value = ctx.input("separator")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome
    if value is None:
        return None
    return str(value)


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
            failures={"os_error": "append_blocked", "nonzero": "append_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if outcome.status == "append_blocked" and (
            "could not resolve to an issue" in text or "issue not found" in text or "not found" in text
        ):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_body_append.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail(
            code="append_blocked",
            summary="Inspecting GitHub issue failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.issue_lookup_failed",
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
            code="append_blocked",
            summary="GitHub issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.invalid_json",
                    level="error",
                    message="GitHub issue output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(payload, dict):
        return fail(
            code="append_blocked",
            summary="GitHub issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.invalid_shape",
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
            code="append_blocked",
            summary="GitHub issue output was missing required fields",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.missing_fields",
                    level="error",
                    message="GitHub issue output was missing required fields",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    return {"body": body, "url": url, "raw": command.raw}
