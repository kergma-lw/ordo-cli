"""git.index.add_all action."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok


def info():
    return action(
        name="index.add_all",
        effects=("stage all current worktree changes into the index",),
        outputs={"staged": "boolean"},
        failure_modes=("stage_blocked",),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    try:
        command = ctx.command(["git", "add", "-A"], failures={"os_error": "stage_blocked", "nonzero": "stage_blocked"})
    except MappedOutcomeError as exc:
        return fail_with_diagnostic(
            code="stage_blocked",
            summary="Staging all worktree changes failed",
            diagnostic_code="action.git.index_add_all_blocked",
            reference=ctx.reference,
            raw=exc.outcome.raw,
        )

    return ok(
        summary="Staged all worktree changes",
        outputs={"staged": True},
        raw=command.raw,
    )
