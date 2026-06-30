"""git.branch probe."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="branch",
        outputs={"value": "string"},
        failure_modes=("probe_failed",),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    repository_root = ctx.bootstrap().context.get("repository_root")
    command = ctx.command(
        ["git", "branch", "--show-current"],
        failures={
            "os_error": "probe_failed",
            "nonzero": "probe_failed",
        },
    )

    branch = command.stdout.strip()
    return ok(
        summary="Current branch inspected successfully",
        outputs={"value": branch, "repository_root": repository_root},
        raw=command.raw,
    )
