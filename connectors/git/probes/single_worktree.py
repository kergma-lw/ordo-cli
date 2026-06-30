"""git.single_worktree probe."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 30

OPERATION = OperationContract(
    name="single_worktree",
    kind="probe",
    outputs={"single_worktree": "boolean", "worktree_count": "integer"},
    failure_modes=("git_unavailable", "not_repository", "probe_failed"),
)


def evaluate(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="probe")
