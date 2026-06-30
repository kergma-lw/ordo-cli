"""gh.issue.view probe."""

from __future__ import annotations

import json

from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="issue.view",
        inputs={"issue": "string"},
        outputs={"issue": "object", "project_items": ["object"]},
        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    issue = str(ctx.input("issue"))
    command = ctx.command(
        ["gh", "issue", "view", issue, "--json", "number,title,state,body,url"],
        failures={
            "os_error": "gh_unavailable",
            "nonzero": "probe_failed",
        },
    )

    try:
        issue_data = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="probe_failed",
            summary="GitHub issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue_view.invalid_json",
                    level="error",
                    message="GitHub issue output was not valid JSON",
                    details={"reference": ctx.reference, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    return ok(
        summary="GitHub issue retrieved successfully",
        outputs={"issue": issue_data},
        raw=command.raw,
    )
