"""git.branch.create action."""

from __future__ import annotations

from connectors.git.actions._shared import BRANCH_INVENTORY_INVALIDATION, head_commit, require_branch_name, require_commit, require_local_branch
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok


def info():
    return action(
        name="branch.create",
        inputs={"branch": "string", "start_point": "string | null"},
        effects=("create a new local branch",),
        outputs={"branch": "string", "start_point": "string"},
        failure_modes=("invalid_branch", "branch_exists", "start_point_not_found", "create_blocked"),
        invalidates_observations=BRANCH_INVENTORY_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch = str(ctx.input("branch"))
    start_point_input = _optional_start_point(ctx)
    if isinstance(start_point_input, OperationOutcome):
        return start_point_input

    invalid_branch = require_branch_name(ctx, branch)
    if invalid_branch is not None:
        return invalid_branch

    existing_branch = require_local_branch(ctx, branch)
    if existing_branch is None:
        return fail_with_diagnostic(
            code="branch_exists",
            summary=f"Local branch '{branch}' already exists",
            diagnostic_code="action.git.branch_exists",
            reference=ctx.reference,
        )

    if start_point_input is None:
        start_point = head_commit(ctx)
        if isinstance(start_point, OperationOutcome):
            return start_point
        command_argv = ["git", "branch", branch]
    else:
        start_point = require_commit(
            ctx,
            start_point_input,
            code="start_point_not_found",
            summary=f"Start point '{start_point_input}' was not found",
            diagnostic_code="action.git.start_point_not_found",
        )
        if isinstance(start_point, OperationOutcome):
            return start_point
        command_argv = ["git", "branch", branch, start_point_input]

    try:
        command = ctx.command(command_argv, failures={"os_error": "create_blocked", "nonzero": "create_blocked"})
    except MappedOutcomeError as exc:
        return fail_with_diagnostic(
            code="create_blocked",
            summary=f"Creating branch '{branch}' failed",
            diagnostic_code="action.git.branch_create_blocked",
            reference=ctx.reference,
            raw=exc.outcome.raw,
        )

    return ok(
        summary=f"Created branch '{branch}'",
        outputs={"branch": branch, "start_point": start_point},
        raw=command.raw,
    )


def _optional_start_point(ctx: OperationContext) -> str | None | OperationOutcome:
    try:
        value = ctx.input("start_point")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome
    if value is None:
        return None
    return str(value)
