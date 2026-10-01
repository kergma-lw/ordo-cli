"""git.commit.revert action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git commit revert',
 'goal': 'A workflow needs to undo one existing commit through an explicit compensating commit instead of rewriting '
         'shared history.',
 'summary': 'Create one new Git commit that reverts one target commit while preserving history, and return both the '
            'reverted commit id and the new revert commit id.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to undo one existing commit through an explicit compensating commit instead '
                         'of rewriting shared history.',
                         'Later steps need the new revert commit id and the resolved target commit id for publication '
                         'or follow-up review.']},
              {'heading': 'Result and boundary',
               'items': ['On success, history gains one new commit that reverses the selected commit while retaining the '
                         'original commit in history.',
                         'Conflicts, unsupported merge commits, or other Git blocks do not produce a completed revert '
                         'result.']},
              {'heading': 'Do not use for',
               'items': ['Rewriting the current HEAD commit; use connector.git.commit.amend when the real intent is an '
                         'amend.',
                         'Creating a normal new commit from currently staged work; use connector.git.commit.create for '
                         'standard commit creation.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.commit.create',
                               'summary': 'Sibling action for recording staged work instead of undoing an older '
                                          'commit'},
                              {'handle': 'connector.git.commit.amend',
                               'summary': 'Sibling action for rewriting HEAD instead of preserving history with a '
                                          'revert commit'},
                              {'handle': 'connector.git.commits',
                                'summary': 'Read recent commit texts before choosing one to revert '
                                          'or after recording the revert'},
                              {'handle': 'connector.git.ref',
                                'summary': 'Resolve an explicit ref when the workflow needs a '
                                          'narrower commit-ref read path'}]},
              {'heading': 'Examples', 'items': ['git.commit.revert with inputs {"commit": "HEAD~1"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.commits', 'connector.git.commit.create', 'connector.git.ref']}]})

def info():
    return action(
        name="commit.revert",
        human=git_human(HUMAN, provide="`commit`: required; identify the non-merge commit to undo. Confirm that reverting this one commit is the intended history change before invoking the action.", result="Returns reverted_commit, revert_commit, and branch. A missing target, merge commit, conflict, or other block does not produce a completed revert result; resolve any conflict before another history action."),
        inputs={"commit": "string"},
        effects=("create a new commit that reverts a target commit",),
        outputs={"reverted_commit": "string", "revert_commit": "string", "branch": "string | null"},
        failure_modes=("commit_not_found", "merge_commit_not_supported", "revert_conflict", "revert_blocked"),
        invalidates_observations=COMMIT_GRAPH_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    commit_ref = str(ctx.input("commit"))
    branch = current_branch(ctx)
    if isinstance(branch, OperationOutcome):
        return branch

    reverted_commit = require_commit(
        ctx,
        commit_ref,
        code="commit_not_found",
        summary=f"Commit '{commit_ref}' was not found",
        diagnostic_code="action.git.commit_not_found",
    )
    if isinstance(reverted_commit, OperationOutcome):
        return reverted_commit

    try:
        command = ctx.command(["git", "revert", "--no-edit", commit_ref], failures={"os_error": "revert_blocked", "nonzero": "revert_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                (
                    "is a merge but no -m option was given",
                    "merge_commit_not_supported",
                    f"Commit '{commit_ref}' is a merge commit and is not supported by this revert action",
                    "action.git.revert_merge_commit_not_supported",
                ),
                (
                    "could not revert",
                    "revert_conflict",
                    f"Reverting commit '{commit_ref}' produced conflicts",
                    "action.git.revert_conflict",
                ),
                (
                    "after resolving the conflicts",
                    "revert_conflict",
                    f"Reverting commit '{commit_ref}' produced conflicts",
                    "action.git.revert_conflict",
                ),
            ),
            fallback_summary=f"Reverting commit '{commit_ref}' failed",
        )

    revert_commit = head_commit(ctx)
    if isinstance(revert_commit, OperationOutcome):
        return revert_commit

    return ok(
        summary=f"Reverted commit '{commit_ref}'",
        outputs={"reverted_commit": reverted_commit, "revert_commit": revert_commit, "branch": branch},
        raw=command.raw,
    )
