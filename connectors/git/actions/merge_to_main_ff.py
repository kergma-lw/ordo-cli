"""git.merge_to_main_ff action."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, action, not_implemented


def info():
    return action(
        name="merge_to_main_ff",
        effects=("fast-forward current work into main",),
        outputs={"merged": "boolean", "base_branch": "string"},
        failure_modes=("non_fast_forward", "action_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="action")
