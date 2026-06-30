"""gh.issue_status_not_in probe."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, not_implemented, probe


def info():
    return probe(
        name="issue_status_not_in",
        inputs={"issue": "string", "statuses": ["string"]},
        outputs={"status": "string", "allowed": "boolean"},
        failure_modes=("issue_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="probe")
