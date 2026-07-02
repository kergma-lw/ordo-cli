"""git.integrate.cherry_pick action."""

from __future__ import annotations

from connectors.git.actions._shared import current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok


def info():
    return action(
        name="integrate.cherry_pick",
        inputs={"commit": "string"},
        effects=("apply a target commit onto the current checkout as a new commit",),
        outputs={"picked_commit": "string", "head_commit": "string", "branch": "string | null"},
        failure_modes=("commit_not_found", "merge_commit_not_supported", "cherry_pick_conflict", "cherry_pick_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    commit_ref = str(ctx.input("commit"))
    branch = current_branch(ctx)
    if isinstance(branch, OperationOutcome):
        return branch

    picked_commit = require_commit(
        ctx,
        commit_ref,
        code="commit_not_found",
        summary=f"Commit '{commit_ref}' was not found",
        diagnostic_code="action.git.cherry_pick_not_found",
    )
    if isinstance(picked_commit, OperationOutcome):
        return picked_commit

    try:
        command = ctx.command(["git", "cherry-pick", commit_ref], failures={"os_error": "cherry_pick_blocked", "nonzero": "cherry_pick_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                (
                    "is a merge but no -m option was given",
                    "merge_commit_not_supported",
                    f"Commit '{commit_ref}' is a merge commit and is not supported by this cherry-pick action",
                    "action.git.cherry_pick_merge_commit_not_supported",
                ),
                ("after resolving the conflicts", "cherry_pick_conflict", f"Cherry-picking commit '{commit_ref}' produced conflicts", "action.git.cherry_pick_conflict"),
                ("could not apply", "cherry_pick_conflict", f"Cherry-picking commit '{commit_ref}' produced conflicts", "action.git.cherry_pick_conflict"),
            ),
            fallback_summary=f"Cherry-picking commit '{commit_ref}' failed",
        )

    merged_head = head_commit(ctx)
    if isinstance(merged_head, OperationOutcome):
        return merged_head

    return ok(
        summary=f"Cherry-picked commit '{commit_ref}'",
        outputs={"picked_commit": picked_commit, "head_commit": merged_head, "branch": branch},
        raw=command.raw,
    )
