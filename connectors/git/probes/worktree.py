"""git.worktree probe."""

from connectors._shared import run_command
from ordo.model.connector import OperationContract
from ordo.model.runtime import OperationResult

ORDER = 70

OPERATION = OperationContract(
    name="worktree",
    kind="probe",
    outputs={"clean": "boolean", "dirty_paths": ["string"]},
    failure_modes=("git_unavailable", "not_repository", "probe_failed"),
)


def evaluate(resolved, workflow) -> OperationResult:
    _ = workflow
    result = run_command(["git", "status", "--porcelain"], reference=resolved.reference)
    if result.status != "ok":
        return result

    stdout = str(result.raw.get("stdout", ""))
    dirty_paths = [line[3:] for line in stdout.splitlines() if len(line) >= 4]
    return OperationResult(
        status="ok",
        summary="Git worktree inspected successfully",
        observations={"clean": not dirty_paths, "dirty_paths": dirty_paths},
        raw=result.raw,
    )
