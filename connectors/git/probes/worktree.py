"""git.worktree probe."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="worktree",
        outputs={"clean": "boolean", "dirty_paths": ["string"]},
        failure_modes=("probe_failed",),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    repository_root = ctx.bootstrap().context.get("repository_root")
    command = ctx.command(
        ["git", "status", "--porcelain"],
        failures={
            "os_error": "probe_failed",
            "nonzero": "probe_failed",
        },
    )

    dirty_paths = [line[3:] for line in command.stdout.splitlines() if len(line) >= 4]
    return ok(
        summary="Git worktree inspected successfully",
        outputs={"clean": not dirty_paths, "dirty_paths": dirty_paths, "repository_root": repository_root},
        raw=command.raw,
    )
