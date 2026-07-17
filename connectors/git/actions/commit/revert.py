"""git.commit.revert action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok


def info():
    return action(
        name="commit.revert",
        inputs={"commit": "string"},
        effects=("create a new commit that reverts a target commit",),
        outputs={"reverted_commit": "string", "revert_commit": "string", "branch": "string | null"},
        failure_modes=("commit_not_found", "merge_commit_not_supported", "revert_conflict", "revert_blocked"),
        invalidates_observations=COMMIT_GRAPH_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    commit_ref = str(ctx.input("commit"))
    branch = current_branch(ctx)
    if isinstance(branch, OperationOutcome):
        return branch

    reverted_commit = require_commit(
        ctx,
        commit_ref,
        code="commit_not_found",
        summary=f"Commit '{commit_ref}' was not found",
        diagnostic_code="action.git.commit_not_found",
    )
    if isinstance(reverted_commit, OperationOutcome):
        return reverted_commit

    try:
        command = ctx.command(["git", "revert", "--no-edit", commit_ref], failures={"os_error": "revert_blocked", "nonzero": "revert_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                (
                    "is a merge but no -m option was given",
                    "merge_commit_not_supported",
                    f"Commit '{commit_ref}' is a merge commit and is not supported by this revert action",
                    "action.git.revert_merge_commit_not_supported",
                ),
                (
                    "could not revert",
                    "revert_conflict",
                    f"Reverting commit '{commit_ref}' produced conflicts",
                    "action.git.revert_conflict",
                ),
                (
                    "after resolving the conflicts",
                    "revert_conflict",
                    f"Reverting commit '{commit_ref}' produced conflicts",
                    "action.git.revert_conflict",
                ),
            ),
            fallback_summary=f"Reverting commit '{commit_ref}' failed",
        )

    revert_commit = head_commit(ctx)
    if isinstance(revert_commit, OperationOutcome):
        return revert_commit

    return ok(
        summary=f"Reverted commit '{commit_ref}'",
        outputs={"reverted_commit": reverted_commit, "revert_commit": revert_commit, "branch": branch},
        raw=command.raw,
    )
