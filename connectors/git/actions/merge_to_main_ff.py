"""git.merge_to_main_ff action."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 60

OPERATION = OperationContract(
    name="merge_to_main_ff",
    kind="action",
    effects=("fast-forward current work into main",),
    outputs={"merged": "boolean", "base_branch": "string"},
    failure_modes=("git_unavailable", "not_repository", "non_fast_forward", "action_failed"),
)


def execute(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="action")
