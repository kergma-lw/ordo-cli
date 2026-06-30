"""git.clean_worktree probe."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, probe


def info():
    return probe(
        name="clean_worktree",
        outputs={"clean": "boolean", "dirty_paths": ["string"]},
        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    return ctx.call("worktree")
