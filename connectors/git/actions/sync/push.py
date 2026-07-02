"""git.sync.push action."""

from __future__ import annotations

from connectors.git.actions._shared import map_nonzero, require_local_branch
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok


def info():
    return action(
        name="sync.push",
        inputs={"branch": "string", "remote": "string | null"},
        effects=("push a local branch to a remote",),
        outputs={"remote": "string", "branch": "string"},
        failure_modes=("branch_not_found", "remote_not_found", "upstream_remote_missing", "non_fast_forward", "push_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch = str(ctx.input("branch"))

    missing_branch = require_local_branch(ctx, branch)
    if missing_branch is not None:
        return missing_branch

    remote = _optional_remote(ctx)
    if isinstance(remote, OperationOutcome):
        return remote
    if remote is None:
        remote = _resolve_upstream_remote(ctx, branch)
        if isinstance(remote, OperationOutcome):
            return remote

    try:
        command = ctx.command(["git", "push", remote, branch], failures={"os_error": "push_blocked", "nonzero": "push_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                ("does not appear to be a git repository", "remote_not_found", f"Remote '{remote}' was not found", "action.git.remote_not_found"),
                ("non-fast-forward", "non_fast_forward", f"Push of branch '{branch}' to remote '{remote}' was rejected as non-fast-forward", "action.git.push_non_fast_forward"),
                ("fetch first", "non_fast_forward", f"Push of branch '{branch}' to remote '{remote}' requires fetching first", "action.git.push_non_fast_forward"),
            ),
            fallback_summary=f"Pushing branch '{branch}' to remote '{remote}' failed",
        )

    return ok(
        summary=f"Pushed branch '{branch}' to remote '{remote}'",
        outputs={"remote": remote, "branch": branch},
        raw=command.raw,
    )


def _optional_remote(ctx: OperationContext) -> str | None | OperationOutcome:
    try:
        value = ctx.input("remote")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome
    if value is None:
        return None
    return str(value)


def _resolve_upstream_remote(ctx: OperationContext, branch: str) -> str | OperationOutcome:
    upstream = ctx.call("upstream")
    if upstream.status != "ok":
        return upstream

    configured = upstream.outputs.get("configured")
    upstream_branch = upstream.outputs.get("branch")
    remote = upstream.outputs.get("remote")
    if configured is True and upstream_branch == branch and isinstance(remote, str) and remote.strip():
        return remote

    return fail_with_diagnostic(
        code="upstream_remote_missing",
        summary=f"Branch '{branch}' does not have a configured upstream remote",
        diagnostic_code="action.git.upstream_remote_missing",
        reference=ctx.reference,
        raw={"upstream": dict(upstream.raw)},
    )
