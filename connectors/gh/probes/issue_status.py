"""gh.issue_status probe."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, not_implemented, probe


def info():
    return probe(
        name="issue_status",
        inputs={"issue": "string", "equals": "string"},
        outputs={"status": "string", "matches": "boolean"},
        failure_modes=("issue_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="probe")
