"""git.clean_worktree probe."""

from connectors.git.probes.worktree import evaluate as evaluate_worktree
from ordo.model.connector import OperationContract

ORDER = 10

OPERATION = OperationContract(
    name="clean_worktree",
    kind="probe",
    outputs={"clean": "boolean", "dirty_paths": ["string"]},
    failure_modes=("git_unavailable", "not_repository", "probe_failed"),
)


def evaluate(resolved, workflow):
    return evaluate_worktree(resolved, workflow)
