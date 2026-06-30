"""gh.issue_status_not_in probe."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 30

OPERATION = OperationContract(
    name="issue_status_not_in",
    kind="probe",
    inputs={"issue": "string", "statuses": ["string"]},
    outputs={"status": "string", "allowed": "boolean"},
    failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
)


def evaluate(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="probe")
