"""git.branch_not_main probe."""

from connectors._shared import run_command
from ordo.model.connector import OperationContract
from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import OperationResult

ORDER = 20

OPERATION = OperationContract(
    name="branch_not_main",
    kind="probe",
    outputs={"allowed": "boolean", "current_branch": "string"},
    failure_modes=("git_unavailable", "not_repository", "probe_failed"),
)


def evaluate(resolved, workflow) -> OperationResult:
    _ = workflow
    result = run_command(["git", "branch", "--show-current"], reference=resolved.reference)
    if result.status != "ok":
        return result

    branch = str(result.raw.get("stdout", "")).strip()
    return OperationResult(
        status="ok" if branch != "main" else "guard_failed",
        summary="Current branch inspected successfully",
        observations={"allowed": branch != "main", "current_branch": branch},
        raw=result.raw,
        diagnostics=() if branch != "main" else (
            Diagnostic(
                code="guard.branch_main",
                level="error",
                message="Current branch is main",
                path=(),
                details={"reference": resolved.reference, "current_branch": branch},
            ),
        ),
    )
