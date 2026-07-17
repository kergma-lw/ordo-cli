"""git.integrate.rebase_onto action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok


def info():
    return action(
        name="integrate.rebase_onto",
        inputs={"onto": "string", "upstream": "string", "branch": "string"},
        effects=("rebase a non-default branch range onto a new base using rebase --onto semantics",),
        outputs={"branch": "string", "onto": "string", "head_commit": "string"},
        failure_modes=("onto_not_found", "upstream_not_found", "branch_not_found", "default_branch_protected", "rebase_conflict", "rebase_blocked"),
        invalidates_observations=COMMIT_GRAPH_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    onto = str(ctx.input("onto"))
    upstream = str(ctx.input("upstream"))
    branch = str(ctx.input("branch"))
    current = current_branch(ctx)
    if isinstance(current, OperationOutcome):
        return current

    resolved_onto = require_commit(
        ctx,
        onto,
        code="onto_not_found",
        summary=f"Base ref '{onto}' was not found",
        diagnostic_code="action.git.rebase_onto_missing",
    )
    if isinstance(resolved_onto, OperationOutcome):
        return resolved_onto

    resolved_upstream = require_commit(
        ctx,
        upstream,
        code="upstream_not_found",
        summary=f"Upstream ref '{upstream}' was not found",
        diagnostic_code="action.git.rebase_upstream_not_found",
    )
    if isinstance(resolved_upstream, OperationOutcome):
        return resolved_upstream

    resolved_branch = require_commit(
        ctx,
        branch,
        code="branch_not_found",
        summary=f"Branch ref '{branch}' was not found",
        diagnostic_code="action.git.rebase_branch_not_found",
    )
    if isinstance(resolved_branch, OperationOutcome):
        return resolved_branch

    repo = ctx.call("repo")
    if repo.status != "ok":
        return repo

    default_branch = repo.outputs.get("default_branch")
    if isinstance(default_branch, str) and default_branch == branch:
        return fail_with_diagnostic(
            code="default_branch_protected",
            summary=f"Branch '{branch}' is the repository default branch and cannot be rebased by this action",
            diagnostic_code="action.git.default_branch_protected",
            reference=ctx.reference,
            raw={"repo": dict(repo.raw)},
        )

    try:
        command = ctx.command(
            ["git", "rebase", "--onto", onto, upstream, branch],
            failures={"os_error": "rebase_blocked", "nonzero": "rebase_blocked"},
        )
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                ("could not apply", "rebase_conflict", f"Rebasing branch '{branch}' onto '{onto}' produced conflicts", "action.git.rebase_conflict"),
                ("resolve all conflicts manually", "rebase_conflict", f"Rebasing branch '{branch}' onto '{onto}' produced conflicts", "action.git.rebase_conflict"),
            ),
            fallback_summary=f"Rebasing branch '{branch}' onto '{onto}' failed",
        )

    rebased_head = head_commit(ctx)
    if isinstance(rebased_head, OperationOutcome):
        return rebased_head

    return ok(
        summary=f"Rebased branch '{branch}' onto '{onto}'",
        outputs={"branch": branch, "onto": resolved_onto, "head_commit": rebased_head},
        raw={**command.raw, "previous_branch": current, "upstream": resolved_upstream, "branch_ref": resolved_branch},
    )
