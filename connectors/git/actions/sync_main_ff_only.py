"""git.sync_main_ff_only action."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, action, not_implemented


def info():
    return action(
        name="sync_main_ff_only",
        effects=("fast-forward main branch",),
        outputs={"synced": "boolean", "base_branch": "string"},
        failure_modes=("git_unavailable", "not_repository", "non_fast_forward", "action_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="action")
