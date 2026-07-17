"""git.branch.delete action."""

from __future__ import annotations

from connectors.git.actions._shared import BRANCH_INVENTORY_INVALIDATION, current_branch, map_nonzero, require_local_branch
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok


def info():
    return action(
        name="branch.delete",
        inputs={"branch": "string"},
        effects=("delete a local non-default branch",),
        outputs={"branch": "string"},
        failure_modes=("branch_not_found", "branch_checked_out", "default_branch_protected", "branch_not_merged", "delete_blocked"),
        invalidates_observations=BRANCH_INVENTORY_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch = str(ctx.input("branch"))
    active_branch = current_branch(ctx)
    if isinstance(active_branch, OperationOutcome):
        return active_branch

    if active_branch == branch:
        return fail_with_diagnostic(
            code="branch_checked_out",
            summary=f"Branch '{branch}' is currently checked out and cannot be deleted",
            diagnostic_code="action.git.branch_checked_out",
            reference=ctx.reference,
        )

    missing_branch = require_local_branch(ctx, branch)
    if missing_branch is not None:
        return missing_branch

    repo = ctx.call("repo")
    if repo.status != "ok":
        return repo

    default_branch = repo.outputs.get("default_branch")
    if isinstance(default_branch, str) and default_branch == branch:
        return fail_with_diagnostic(
            code="default_branch_protected",
            summary=f"Branch '{branch}' is the repository default branch and cannot be deleted",
            diagnostic_code="action.git.default_branch_protected",
            reference=ctx.reference,
            raw={"repo": dict(repo.raw)},
        )

    try:
        command = ctx.command(["git", "branch", "-d", branch], failures={"os_error": "delete_blocked", "nonzero": "delete_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                (
                    "checked out at",
                    "branch_checked_out",
                    f"Branch '{branch}' is checked out in a worktree and cannot be deleted",
                    "action.git.branch_checked_out",
                ),
                (
                    "cannot delete branch",
                    "branch_checked_out",
                    f"Branch '{branch}' is currently checked out and cannot be deleted",
                    "action.git.branch_checked_out",
                ),
                (
                    "not fully merged",
                    "branch_not_merged",
                    f"Branch '{branch}' is not fully merged",
                    "action.git.branch_not_merged",
                ),
            ),
            fallback_summary=f"Deleting branch '{branch}' failed",
        )

    return ok(
        summary=f"Deleted branch '{branch}'",
        outputs={"branch": branch},
        raw=command.raw,
    )
