"""git.branch probe."""

from connectors._shared import run_command
from ordo.model.connector import OperationContract
from ordo.model.runtime import OperationResult

ORDER = 80

OPERATION = OperationContract(
    name="branch",
    kind="probe",
    outputs={"value": "string"},
    failure_modes=("git_unavailable", "not_repository", "probe_failed"),
)


def evaluate(resolved, workflow) -> OperationResult:
    _ = workflow
    result = run_command(["git", "branch", "--show-current"], reference=resolved.reference)
    if result.status != "ok":
        return result

    branch = str(result.raw.get("stdout", "")).strip()
    return OperationResult(
        status="ok",
        summary="Current branch inspected successfully",
        observations={"value": branch},
        raw=result.raw,
    )
