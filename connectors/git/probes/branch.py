"""git.branch probe."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="branch",
        outputs={"value": "string"},
        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    command = ctx.command(
        ["git", "branch", "--show-current"],
        failures={
            "os_error": "git_unavailable",
            "nonzero": "probe_failed",
        },
    )

    branch = command.stdout.strip()
    return ok(
        summary="Current branch inspected successfully",
        outputs={"value": branch},
        raw=command.raw,
    )
