"""git.branch.switch action."""

from __future__ import annotations

from connectors.git.actions._shared import current_branch, map_nonzero, require_local_branch
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok


def info():
    return action(
        name="branch.switch",
        inputs={"branch": "string"},
        effects=("switch current checkout to a local branch",),
        outputs={"branch": "string", "changed": "boolean"},
        failure_modes=("branch_not_found", "worktree_change_conflict", "unresolved_state", "switch_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch = str(ctx.input("branch"))
    previous_branch = current_branch(ctx)
    if isinstance(previous_branch, OperationOutcome):
        return previous_branch

    missing_branch = require_local_branch(ctx, branch)
    if missing_branch is not None:
        return missing_branch

    try:
        command = ctx.command(["git", "switch", branch], failures={"os_error": "action_failed", "nonzero": "action_failed"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                (
                    "would be overwritten by checkout",
                    "worktree_change_conflict",
                    f"Switching to branch '{branch}' would overwrite local changes",
                    "action.git.branch_switch_worktree_conflict",
                ),
                (
                    "you need to resolve your current index first",
                    "unresolved_state",
                    f"Switching to branch '{branch}' is blocked by index conflicts",
                    "action.git.branch_switch_unresolved_state",
                ),
                (
                    "you are in the middle of a merge",
                    "unresolved_state",
                    f"Switching to branch '{branch}' is blocked by an unresolved repository state",
                    "action.git.branch_switch_unresolved_state",
                ),
            ),
            fallback_summary=f"Switching to branch '{branch}' failed",
        )

    changed = previous_branch != branch
    return ok(
        summary=f"Switched to branch '{branch}'" if changed else f"Branch '{branch}' was already current",
        outputs={"branch": branch, "changed": changed},
        raw=command.raw,
    )
