"""GitHub family bootstrap contract."""

from ordo.plugin_sdk import bootstrap, bootstrap_ok
from ordo.model.connector import ConnectorBootstrap

BOOTSTRAP = ConnectorBootstrap(
    prerequisites=("gh binary available", "GitHub auth available"),
    context_fields=("host", "viewer", "scopes"),
)


def info():
    return bootstrap(
        prerequisites=BOOTSTRAP.prerequisites,
        context_fields=BOOTSTRAP.context_fields,
        handler=run,
    )


def run(ctx):
    command = ctx.command(
        ["gh", "auth", "status"],
        failures={
            "os_error": "gh_unavailable",
            "nonzero": "auth_missing",
        },
    )
    return bootstrap_ok(
        summary="GitHub bootstrap completed successfully",
        context={"host": "github.com", "viewer": None, "scopes": []},
        raw=command.raw,
    )
