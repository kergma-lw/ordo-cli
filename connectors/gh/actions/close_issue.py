"""gh.close_issue action."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 70

OPERATION = OperationContract(
    name="close_issue",
    kind="action",
    inputs={"issue": "string"},
    effects=("close GitHub issue",),
    outputs={"issue": "string", "closed": "boolean"},
    failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "action_failed"),
)


def execute(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="action")
