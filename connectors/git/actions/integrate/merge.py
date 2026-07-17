"""git.integrate.merge action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok


def info():
    return action(
        name="integrate.merge",
        inputs={"ref": "string"},
        effects=("integrate a target ref into the current checkout using merge semantics",),
        outputs={"merged_ref": "string", "head_commit": "string", "branch": "string | null"},
        failure_modes=("ref_not_found", "merge_conflict", "merge_blocked"),
        invalidates_observations=COMMIT_GRAPH_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    ref = str(ctx.input("ref"))
    branch = current_branch(ctx)
    if isinstance(branch, OperationOutcome):
        return branch

    resolved_ref = require_commit(
        ctx,
        ref,
        code="ref_not_found",
        summary=f"Ref '{ref}' was not found",
        diagnostic_code="action.git.merge_ref_not_found",
    )
    if isinstance(resolved_ref, OperationOutcome):
        return resolved_ref

    try:
        command = ctx.command(
            ["git", "merge", "--no-ff", "--no-edit", ref],
            failures={"os_error": "merge_blocked", "nonzero": "merge_blocked"},
        )
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                ("automatic merge failed", "merge_conflict", f"Merging ref '{ref}' produced conflicts", "action.git.merge_conflict"),
                ("fix conflicts and then commit the result", "merge_conflict", f"Merging ref '{ref}' produced conflicts", "action.git.merge_conflict"),
            ),
            fallback_summary=f"Merging ref '{ref}' failed",
        )

    merged_head = head_commit(ctx)
    if isinstance(merged_head, OperationOutcome):
        return merged_head

    return ok(
        summary=f"Merged ref '{ref}' into the current checkout",
        outputs={"merged_ref": resolved_ref, "head_commit": merged_head, "branch": branch},
        raw=command.raw,
    )
