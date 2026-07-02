"""gh.issue package and operation."""

from __future__ import annotations

import json

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe

ISSUE_JSON_FIELDS = (
    "id",
    "number",
    "title",
    "state",
    "closed",
    "url",
    "body",
    "author",
    "labels",
    "assignees",
    "milestone",
    "createdAt",
    "updatedAt",
    "closedAt",
    "comments",
    "reactionGroups",
    "repository",
    "stateReason",
    "projectItems",
)

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
    "createdAt": "string",
    "updatedAt": "string",
    "closedAt": "string",
    "comments": "object",
    "reactionGroups": ["object"],
    "repository": "object",
    "stateReason": "string",
    "projectItems": ["object"],
}


def info():
    return probe(
        name="issue",
        inputs={"issue": "string"},
        outputs=ISSUE_OUTPUTS,
        failure_modes=("issue_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    issue = str(ctx.input("issue"))

    try:
        command = ctx.command(
            ["gh", "issue", "view", issue, "--json", ",".join(ISSUE_JSON_FIELDS)],
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
                        details={"reference": ctx.reference, "issue": issue},
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
                        details={"reference": ctx.reference, "issue": issue},
                    ),
                ),
                raw=outcome.raw,
            )
        return outcome

    try:
        issue_data = json.loads(command.stdout) if command.stdout else {}
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

    if not isinstance(issue_data, dict):
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
        outputs=issue_data,
        raw=command.raw,
    )
