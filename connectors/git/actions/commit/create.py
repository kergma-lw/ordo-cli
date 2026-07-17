"""git.commit.create action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok


def info():
    return action(
        name="commit.create",
        inputs={"message": "string"},
        effects=("create a new commit from the current index",),
        outputs={"commit": "string", "branch": "string | null"},
        failure_modes=("message_invalid", "nothing_to_commit", "commit_blocked"),
        invalidates_observations=COMMIT_GRAPH_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    message = str(ctx.input("message"))
    if not message.strip():
        return fail_with_diagnostic(
            code="message_invalid",
            summary="Commit message must not be empty",
            diagnostic_code="action.git.commit_message_invalid",
            reference=ctx.reference,
        )

    branch = current_branch(ctx)
    if isinstance(branch, OperationOutcome):
        return branch

    try:
        command = ctx.command(["git", "commit", "-m", message], failures={"os_error": "commit_blocked", "nonzero": "commit_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(("nothing to commit", "nothing_to_commit", "There is nothing to commit", "action.git.nothing_to_commit"),),
            fallback_summary="Creating a commit failed",
        )

    commit = head_commit(ctx)
    if isinstance(commit, OperationOutcome):
        return commit

    return ok(
        summary="Created a new commit",
        outputs={"commit": commit, "branch": branch},
        raw=command.raw,
    )
