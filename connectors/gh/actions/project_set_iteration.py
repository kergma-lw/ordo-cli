"""gh.project_set_iteration action."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 60

OPERATION = OperationContract(
    name="project_set_iteration",
    kind="action",
    inputs={"issue": "string", "value": "string"},
    effects=("update project iteration field",),
    outputs={"issue": "string", "iteration": "string"},
    failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "action_failed"),
)


def execute(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="action")
