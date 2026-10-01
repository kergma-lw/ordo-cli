"""git.commit.create action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git commit create',
 'goal': 'A workflow has already staged the intended changes and now needs one normal commit creation step rather than '
         'history rewriting.',
 'summary': 'Create one new Git commit from the current index with one non-empty commit message and return the new '
            'commit id plus the current branch context.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow has already staged the intended changes and now needs one normal commit creation '
                          'step rather than history rewriting.',
                           'Use this to capture the current index as one new commit and publish the '
                          'resulting commit id for later steps.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the staged changes become one new commit and the resulting revision is available '
                         'to later steps.',
                         'When there is nothing to commit, history is unchanged; this is distinct from a successful '
                         'commit.',
                         'If Git blocks commit creation, no successful commit result is reported.']},
              {'heading': 'What to provide',
               'items': ['Provide a non-empty message that describes the staged change being recorded.']},
              {'heading': 'Do not use for',
               'items': ['Rewriting the current HEAD commit; use connector.git.commit.amend for amend-style history '
                         'rewriting.',
                         'Undoing one existing commit with a compensating revert commit; use '
                         'connector.git.commit.revert for that distinct history-preserving action.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.commit.amend',
                               'summary': 'Sibling action for rewriting the current HEAD commit instead of creating a '
                                          'fresh one'},
                              {'handle': 'connector.git.commit.revert',
                               'summary': 'Sibling action for creating a compensating revert commit instead of '
                                          'recording newly staged changes'},
                              {'handle': 'connector.git.commits',
                                'summary': 'Read recent commit texts before or after commit '
                                          'creation'},
                              {'handle': 'connector.git.worktree',
                                'summary': 'Read broader worktree state when commit readiness depends on '
                                          'unstaged or staged changes'}]},
              {'heading': 'Examples',
               'items': ['git.commit.create with inputs {"message": "Record release notes update"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.commits', 'connector.git.commit.amend', 'connector.git.worktree']}]})

def info():
    return action(
        name="commit.create",
        human=git_human(HUMAN, provide="`message`: required; describe the staged change clearly enough for repository history. Review the staged change first because this action records all staged content in one commit.", result="Returns commit and branch. Empty messages, nothing to commit, or a blocked commit leave no successful commit result."),
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
