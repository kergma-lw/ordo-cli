"""git.sync.fetch action."""

from __future__ import annotations

from connectors.git.actions._shared import map_nonzero
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok


def info():
    return action(
        name="sync.fetch",
        inputs={"remote": "string"},
        effects=("fetch refs from a remote into the local repository",),
        outputs={"remote": "string", "fetched": "boolean"},
        failure_modes=("remote_not_found", "fetch_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    remote = str(ctx.input("remote"))
    try:
        command = ctx.command(["git", "fetch", remote], failures={"os_error": "fetch_blocked", "nonzero": "fetch_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(("does not appear to be a git repository", "remote_not_found", f"Remote '{remote}' was not found", "action.git.remote_not_found"),),
            fallback_summary=f"Fetching from remote '{remote}' failed",
        )

    return ok(
        summary=f"Fetched from remote '{remote}'",
        outputs={"remote": remote, "fetched": True},
        raw=command.raw,
    )
