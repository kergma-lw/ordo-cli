"""gh.issue_project_membership probe."""

from connectors._shared import not_implemented
from ordo.model.connector import OperationContract

ORDER = 40

OPERATION = OperationContract(
    name="issue_project_membership",
    kind="probe",
    inputs={"issue": "string"},
    outputs={"member": "boolean", "project_items": ["object"]},
    failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
)


def evaluate(resolved, workflow):
    _ = workflow
    return not_implemented(resolved.reference, kind="probe")
