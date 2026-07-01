"""Git family bootstrap contract."""

from ordo.plugin_sdk import Diagnostic, bootstrap, bootstrap_fail, bootstrap_ok
from ordo.model.connector import ConnectorBootstrap

BOOTSTRAP = ConnectorBootstrap(
    prerequisites=("git binary available", "inside git repository"),
    context_fields=("repository_root",),
)


def info():
    return bootstrap(
        prerequisites=BOOTSTRAP.prerequisites,
        context_fields=BOOTSTRAP.context_fields,
        handler=run,
    )


def run(ctx):
    command = ctx.command(
        ["git", "rev-parse", "--show-toplevel"],
        failures={
            "os_error": "git_unavailable",
            "nonzero": "not_repository",
        },
    )

    repository_root = command.stdout.strip()
    if not repository_root:
        return bootstrap_fail(
            code="not_repository",
            summary="Repository root could not be determined",
            diagnostics=(
                Diagnostic(
                    code="bootstrap.repository_missing",
                    level="error",
                    message="Repository root could not be determined",
                ),
            ),
            raw=command.raw,
        )

    return bootstrap_ok(
        summary="Git bootstrap completed successfully",
        context={
            "repository_root": repository_root,
        },
        raw=command.raw,
    )
