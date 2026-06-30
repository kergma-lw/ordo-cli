"""Shell family bootstrap contract."""

from ordo.plugin_sdk import Diagnostic, bootstrap, bootstrap_fail, bootstrap_ok
from ordo.model.connector import ConnectorBootstrap

BOOTSTRAP = ConnectorBootstrap(
    prerequisites=("supported shell available",),
    context_fields=("shell", "working_directory"),
)


def info():
    return bootstrap(
        prerequisites=BOOTSTRAP.prerequisites,
        context_fields=BOOTSTRAP.context_fields,
        handler=run,
    )


def run(ctx):
    command = ctx.command(
        ["bash", "-lc", "pwd"],
        failures={
            "os_error": "shell_unavailable",
            "nonzero": "shell_unavailable",
        },
    )
    working_directory = command.stdout.strip()
    if not working_directory:
        return bootstrap_fail(
            code="shell_unavailable",
            summary="Working directory could not be determined",
            diagnostics=(
                Diagnostic(
                    code="bootstrap.shell_workdir_missing",
                    level="error",
                    message="Working directory could not be determined",
                ),
            ),
            raw=command.raw,
        )
    return bootstrap_ok(
        summary="Shell bootstrap completed successfully",
        context={"shell": "bash", "working_directory": working_directory},
        raw=command.raw,
    )
