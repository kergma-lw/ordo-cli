"""gh.project_set_status action."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 50

OPERATION = OperationContract(
    name="project_set_status",
    kind="action",
    inputs={"issue": "string", "status": "string"},
    effects=("update project status field",),
    outputs={"issue": "string", "status": "string"},
    failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "action_failed"),
)


def execute(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="action")
