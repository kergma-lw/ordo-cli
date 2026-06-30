"""gh.close_issue action."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, action, not_implemented


def info():
    return action(
        name="close_issue",
        inputs={"issue": "string"},
        effects=("close GitHub issue",),
        outputs={"issue": "string", "closed": "boolean"},
        failure_modes=("issue_not_found", "action_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="action")
