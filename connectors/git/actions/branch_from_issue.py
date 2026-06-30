"""git.branch_from_issue action."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 50

OPERATION = OperationContract(
    name="branch_from_issue",
    kind="action",
    inputs={"issue": "string", "branch": "string"},
    effects=("create or switch task branch",),
    outputs={"branch": "string", "created": "boolean"},
    failure_modes=("git_unavailable", "not_repository", "invalid_issue", "action_failed"),
)


def execute(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="action")
