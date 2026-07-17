"""git.integrate.merge_ff_only action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok


def info():
    return action(
        name="integrate.merge_ff_only",
        inputs={"ref": "string"},
        effects=("integrate a target ref into the current checkout using fast-forward-only semantics",),
        outputs={"merged_ref": "string", "head_commit": "string", "branch": "string | null"},
        failure_modes=("ref_not_found", "non_fast_forward", "merge_blocked"),
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
        diagnostic_code="action.git.merge_ff_ref_not_found",
    )
    if isinstance(resolved_ref, OperationOutcome):
        return resolved_ref

    try:
        command = ctx.command(["git", "merge", "--ff-only", ref], failures={"os_error": "merge_blocked", "nonzero": "merge_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(("not possible to fast-forward", "non_fast_forward", f"Ref '{ref}' cannot be merged with fast-forward only", "action.git.non_fast_forward"),),
            fallback_summary=f"Fast-forward merge for ref '{ref}' failed",
        )

    merged_head = head_commit(ctx)
    if isinstance(merged_head, OperationOutcome):
        return merged_head

    return ok(
        summary=f"Fast-forward merged ref '{ref}' into the current checkout",
        outputs={"merged_ref": resolved_ref, "head_commit": merged_head, "branch": branch},
        raw=command.raw,
    )
