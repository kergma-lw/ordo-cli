"""git.branch_from_issue action."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, action, not_implemented


def info():
    return action(
        name="branch_from_issue",
        inputs={"issue": "string", "branch": "string"},
        effects=("create or switch task branch",),
        outputs={"branch": "string", "created": "boolean"},
        failure_modes=("git_unavailable", "not_repository", "invalid_issue", "action_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="action")
