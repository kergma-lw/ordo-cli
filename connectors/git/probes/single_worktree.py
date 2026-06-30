"""git.single_worktree probe."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, not_implemented, probe


def info():
    return probe(
        name="single_worktree",
        outputs={"single_worktree": "boolean", "worktree_count": "integer"},
        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return not_implemented(reference=ctx.reference, kind="probe")
