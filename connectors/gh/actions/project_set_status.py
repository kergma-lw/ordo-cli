"""gh.project_set_status action."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, action, not_implemented


def info():
    return action(
        name="project_set_status",
        inputs={"issue": "string", "status": "string"},
        effects=("update project status field",),
        outputs={"issue": "string", "status": "string"},
        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "action_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="action")
