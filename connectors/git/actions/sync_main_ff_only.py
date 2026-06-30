"""git.sync_main_ff_only action."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 40

OPERATION = OperationContract(
    name="sync_main_ff_only",
    kind="action",
    effects=("fast-forward main branch",),
    outputs={"synced": "boolean", "base_branch": "string"},
    failure_modes=("git_unavailable", "not_repository", "non_fast_forward", "action_failed"),
)


def execute(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="action")
