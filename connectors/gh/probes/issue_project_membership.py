"""gh.issue_project_membership probe."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, not_implemented, probe


def info():
    return probe(
        name="issue_project_membership",
        inputs={"issue": "string"},
        outputs={"member": "boolean", "project_items": ["object"]},
        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="probe")
