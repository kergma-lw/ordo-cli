"""git.branch.delete action."""

from __future__ import annotations

from connectors.git.actions._shared import BRANCH_INVENTORY_INVALIDATION, current_branch, map_nonzero, require_local_branch
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git branch delete',
 'goal': 'A workflow is intentionally cleaning up one stale local branch rather than switching branches or resetting '
         'repository state broadly.',
  'summary': 'Delete one local non-default Git branch. Optional strictly boolean force defaults to false: omitted or '
             'false keeps the merged-branch safety check; true bypasses it.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow is intentionally cleaning up one stale local branch rather than switching '
                          'branches or resetting repository state broadly.',
                          'Use the normal merged-branch safety check for ordinary cleanup. Force deletion only after '
                          'the workflow has independently established that removing unmerged local history is intended.',
                          'The action protects the repository default branch and branches checked out in any worktree.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the selected local branch no longer exists.',
                         'A protected, checked-out, or unmerged branch remains in place unless an intentional forced '
                         'deletion is allowed. Other Git blocks do not report that deletion completed.']},
              {'heading': 'Do not use for',
               'items': ['Switching away from the current branch before deletion; use connector.git.branch.switch '
                         'first when the current checkout must move.',
                          'Deleting tags, remote refs, or arbitrary refs; this operation only covers local branch '
                         'cleanup.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.branch',
                                'summary': 'Check whether the target branch is '
                                          'currently active'},
                              {'handle': 'connector.git.branches',
                                'summary': 'List local and remote branches before '
                                          'deletion'},
                              {'handle': 'connector.git.branch.switch',
                               'summary': 'Sibling action for moving off the target branch before deletion if needed'},
                              {'handle': 'connector.git.repo',
                                'summary': 'Read repository-level facts such as the protected default '
                                          'branch'}]},
              {'heading': 'Examples',
               'items': ['git.branch.delete with inputs {"branch": "stale/demo"}',
                         'git.branch.delete with inputs {"branch": "squash/demo", "force": true}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.branches', 'connector.git.branch.switch', 'connector.git.branch']}]})

def info():
    return action(
        name="branch.delete",
        human=git_human(HUMAN, provide="`branch`: required. `force`: optional; omit it or use false for ordinary merged-branch safety, and use true only after confirming unmerged history may be removed.", result="Returns branch after deletion. Missing, default, checked-out, or unmerged branches remain present unless intentional force applies; blocks do not report deletion."),
        summary="Delete a local non-default branch; optional boolean force defaults to false (-d), true uses -D.",
        inputs={"branch": "string", "force": "boolean"},
        effects=("delete a local non-default branch",),
        outputs={"branch": "string"},
        failure_modes=("input_error", "branch_not_found", "branch_checked_out", "default_branch_protected", "branch_not_merged", "delete_blocked"),
        invalidates_observations=BRANCH_INVENTORY_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch = str(ctx.input("branch"))
    try:
        force = ctx.input("force")
    except MappedOutcomeError as exc:
        if not any(diagnostic.code == "operation.input_missing" for diagnostic in exc.outcome.diagnostics):
            return exc.outcome
        force = False
    if type(force) is not bool:
        return fail_with_diagnostic(
            code="input_error",
            summary="Input 'force' must be a boolean when provided",
            diagnostic_code="action.git.branch_delete.invalid_force",
            reference=ctx.reference,
        )
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
        command = ctx.command(["git", "branch", "-D" if force else "-d", branch], failures={"os_error": "delete_blocked", "nonzero": "delete_blocked"})
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
