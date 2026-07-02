"""git.commit.amend action."""

from __future__ import annotations

from connectors.git.actions._shared import current_branch, head_commit, map_nonzero
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok


def info():
    return action(
        name="commit.amend",
        inputs={"message": "string | null"},
        effects=("rewrite the current HEAD commit",),
        outputs={"commit": "string", "previous_commit": "string", "branch": "string | null"},
        failure_modes=("message_invalid", "nothing_to_amend", "amend_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    message = _optional_message(ctx)
    if isinstance(message, OperationOutcome):
        return message

    branch = current_branch(ctx)
    if isinstance(branch, OperationOutcome):
        return branch

    previous_commit = head_commit(ctx)
    if isinstance(previous_commit, OperationOutcome):
        return fail_with_diagnostic(
            code="nothing_to_amend",
            summary="There is no HEAD commit to amend",
            diagnostic_code="action.git.nothing_to_amend",
            reference=ctx.reference,
            raw=previous_commit.raw,
        )

    argv = ["git", "commit", "--amend", "--no-edit"] if message is None else ["git", "commit", "--amend", "-m", message]

    try:
        command = ctx.command(
            argv,
            failures={"os_error": "amend_blocked", "nonzero": "amend_blocked"},
        )
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(("nothing to amend", "nothing_to_amend", "There is no commit state to amend", "action.git.nothing_to_amend"),),
            fallback_summary="Amending the current commit failed",
        )

    commit = head_commit(ctx)
    if isinstance(commit, OperationOutcome):
        return commit

    return ok(
        summary="Amended the current commit",
        outputs={"commit": commit, "previous_commit": previous_commit, "branch": branch},
        raw=command.raw,
    )


def _optional_message(ctx: OperationContext) -> str | None | OperationOutcome:
    try:
        value = ctx.input("message")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome

    if value is None:
        return None

    message = str(value)
    if not message.strip():
        return fail_with_diagnostic(
            code="message_invalid",
            summary="Commit message must not be empty",
            diagnostic_code="action.git.commit_message_invalid",
            reference=ctx.reference,
        )
    return message
