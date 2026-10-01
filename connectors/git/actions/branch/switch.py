"""git.branch.switch action."""

from __future__ import annotations

from connectors.git.actions._shared import CHECKOUT_STATE_INVALIDATION, current_branch, map_nonzero, require_local_branch
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git branch switch',
 'goal': 'A workflow needs to move the current checkout onto one known local branch before later repository actions '
         'run.',
 'summary': 'Switch the current Git checkout to one existing local branch and report whether the checkout actually '
            'changed.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to move the current checkout onto one known local branch before later '
                          'repository actions run.',
                           'Use this to move the checkout, with explicit reporting about whether the '
                          'branch was already current.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the requested local branch is current, with an explicit result when it was '
                         'already checked out.',
                         'Local changes that would be overwritten, unresolved repository state, or other Git blocks do '
                         'not produce a completed switch result.']},
              {'heading': 'Do not use for',
               'items': ['Creating a new branch before switching; use connector.git.branch.create first when the '
                         'target branch may not exist yet.',
                         'Inspecting current branch state without mutating checkout; use connector.git.branch for the '
                          'read-only checkout lookup.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.branch',
                                'summary': 'Read current-branch context before or after '
                                          'switching'},
                              {'handle': 'connector.git.branch.create',
                               'summary': 'Sibling action for creating a branch before switching to it'},
                              {'handle': 'connector.git.worktree',
                                'summary': 'Read broader worktree cleanliness when switch safety depends '
                                          'on local changes'},
                              {'handle': 'connector.git.state',
                                'summary': 'Read broader repository state when branch switching is only '
                                          'part of the decision'}]},
              {'heading': 'Examples', 'items': ['git.branch.switch with inputs {"branch": "feature/demo"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.branch', 'connector.git.worktree', 'connector.git.state']}]})

def info():
    return action(
        name="branch.switch",
        human=git_human(HUMAN, provide="`branch`: required; provide an existing local branch. Confirm that switching the current checkout to this branch is safe for the next workflow step.", result="Returns branch and changed, where changed=false means it was already current. Missing branch, conflicting local changes, unresolved state, or other blocks do not report a completed switch."),
        inputs={"branch": "string"},
        effects=("switch current checkout to a local branch",),
        outputs={"branch": "string", "changed": "boolean"},
        failure_modes=("branch_not_found", "worktree_change_conflict", "unresolved_state", "switch_blocked"),
        invalidates_observations=CHECKOUT_STATE_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch = str(ctx.input("branch"))
    previous_branch = current_branch(ctx)
    if isinstance(previous_branch, OperationOutcome):
        return previous_branch

    missing_branch = require_local_branch(ctx, branch)
    if missing_branch is not None:
        return missing_branch

    try:
        command = ctx.command(["git", "switch", branch], failures={"os_error": "action_failed", "nonzero": "action_failed"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                (
                    "would be overwritten by checkout",
                    "worktree_change_conflict",
                    f"Switching to branch '{branch}' would overwrite local changes",
                    "action.git.branch_switch_worktree_conflict",
                ),
                (
                    "you need to resolve your current index first",
                    "unresolved_state",
                    f"Switching to branch '{branch}' is blocked by index conflicts",
                    "action.git.branch_switch_unresolved_state",
                ),
                (
                    "you are in the middle of a merge",
                    "unresolved_state",
                    f"Switching to branch '{branch}' is blocked by an unresolved repository state",
                    "action.git.branch_switch_unresolved_state",
                ),
            ),
            fallback_summary=f"Switching to branch '{branch}' failed",
        )

    changed = previous_branch != branch
    return ok(
        summary=f"Switched to branch '{branch}'" if changed else f"Branch '{branch}' was already current",
        outputs={"branch": branch, "changed": changed},
        raw=command.raw,
    )
