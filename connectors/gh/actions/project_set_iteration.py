"""gh.project_set_iteration action."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, action, not_implemented


def info():
    return action(
        name="project_set_iteration",
        inputs={"issue": "string", "value": "string"},
        effects=("update project iteration field",),
        outputs={"issue": "string", "iteration": "string"},
        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "action_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="action")
