"""git.worktree probe."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="worktree",
        outputs={"clean": "boolean", "dirty_paths": ["string"]},
        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    command = ctx.command(
        ["git", "status", "--porcelain"],
        failures={
            "os_error": "git_unavailable",
            "nonzero": "probe_failed",
        },
    )

    dirty_paths = [line[3:] for line in command.stdout.splitlines() if len(line) >= 4]
    return ok(
        summary="Git worktree inspected successfully",
        outputs={"clean": not dirty_paths, "dirty_paths": dirty_paths},
        raw=command.raw,
    )
