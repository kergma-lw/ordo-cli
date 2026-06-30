"""gh.issue_status probe."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 20

OPERATION = OperationContract(
    name="issue_status",
    kind="probe",
    inputs={"issue": "string", "equals": "string"},
    outputs={"status": "string", "matches": "boolean"},
    failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
)


def evaluate(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="probe")
