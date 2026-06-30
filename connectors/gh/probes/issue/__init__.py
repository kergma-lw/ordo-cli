"""gh.issue package and operation."""

from __future__ import annotations

import json

from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="issue",
        inputs={"issue": "string"},
        outputs={"status": "string", "project": {"member": "boolean", "items": ["object"]}, "issue": "object"},
        failure_modes=("issue_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    issue = ctx.input("issue")
    command = ctx.command(
        ["gh", "issue", "view", str(issue), "--json", "number,title,state,body,url"],
        failures={
            "os_error": "probe_failed",
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
                    code="probe.gh_issue.invalid_json",
                    level="error",
                    message="GitHub issue output was not valid JSON",
                    details={"reference": ctx.reference, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    return ok(
        summary="GitHub issue retrieved successfully",
        outputs={"issue": issue_data, "status": issue_data.get("state"), "project": {"member": False, "items": []}},
        raw=command.raw,
    )
