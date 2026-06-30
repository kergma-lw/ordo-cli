"""gh.issue package and operation."""

from __future__ import annotations

import json

from connectors._shared import require_expression_input, run_command
from ordo.model.connector import OperationContract
from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import OperationResult

ORDER = 80

OPERATION = OperationContract(
    name="issue",
    kind="probe",
    inputs={"issue": "string"},
    outputs={"status": "string", "project": {"member": "boolean", "items": ["object"]}, "issue": "object"},
    failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
)


def evaluate(resolved, workflow) -> OperationResult:
    issue = require_expression_input(workflow, resolved, "issue")
    if isinstance(issue, OperationResult):
        return issue

    result = run_command(["gh", "issue", "view", str(issue), "--json", "number,title,state,body,url"], reference=resolved.reference)
    if result.status != "ok":
        return result

    stdout = str(result.raw.get("stdout", ""))
    try:
        issue_data = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as exc:
        return OperationResult(
            status="probe_failed",
            summary="GitHub issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue.invalid_json",
                    level="error",
                    message="GitHub issue output was not valid JSON",
                    path=(),
                    details={"reference": resolved.reference, "error": str(exc)},
                ),
            ),
            raw=result.raw,
        )

    return OperationResult(
        status="ok",
        summary="GitHub issue retrieved successfully",
        observations={"issue": issue_data, "status": issue_data.get("state"), "project": {"member": False, "items": []}},
        raw=result.raw,
    )
