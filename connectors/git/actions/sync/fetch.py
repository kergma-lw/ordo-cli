"""git.sync.fetch action."""

from __future__ import annotations

from connectors.git.actions._shared import FETCH_INVALIDATION, map_nonzero
from connectors.git.actions.sync._shared import require_configured_remote
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok


def info():
    return action(
        name="sync.fetch",
        summary="Fetch from a configured remote name, not a direct URL, path, or option",
        inputs={"remote": "string"},
        effects=("fetch refs from a remote into the local repository",),
        outputs={"remote": "string", "fetched": "boolean"},
        failure_modes=("remote_not_found", "fetch_blocked"),
        invalidates_observations=FETCH_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    remote = require_configured_remote(ctx, ctx.input("remote"), "fetch_blocked")
    if isinstance(remote, OperationOutcome):
        return remote
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
