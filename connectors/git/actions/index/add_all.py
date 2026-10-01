"""git.index.add_all action."""

from __future__ import annotations

from connectors.git.actions._shared import INDEX_INVALIDATION
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git index add_all',
 'goal': 'A workflow has already decided that the whole current worktree batch should be staged before one later '
         'commit or review step.',
 'summary': 'Stage every currently changed, deleted, and untracked path from the current Git worktree into the index '
            'as one all-in staging action.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow has already decided that the whole current worktree batch should be staged before '
                         'one later commit or review step.',
                          'Use this to stage the whole worktree, not for selective per-path staging or '
                         'read-only inspection.']},
              {'heading': 'Do not use for',
               'items': ['Inspecting which paths are dirty or whether the worktree is clean; use '
                         'connector.git.worktree or connector.git.state for those read-only checks.',
                          'Selecting only some paths for staging; this operation intentionally stages the whole '
                         'current worktree batch at once.']},
              {'heading': 'Result and boundary',
               'items': ['On success, every current changed, deleted, and untracked path is staged for a later commit.',
                         'If staging is blocked, the action does not report that the worktree batch is ready to commit.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.worktree',
                                'summary': 'Read the path-level dirty-worktree view before or after '
                                          'staging'},
                              {'handle': 'connector.git.state',
                                'summary': 'Read a broader branch-plus-worktree-plus-stash summary after '
                                          'staging decisions'},
                              {'handle': 'connector.git.commit.create',
                               'summary': 'Typical follow-up action for recording the newly staged index as one '
                                          'ordinary commit'},
                              {'handle': 'connector.git.commit.amend',
                               'summary': 'Sibling follow-up action when the staged batch should rewrite HEAD instead '
                                          'of creating a new commit'}]},
              {'heading': 'Examples', 'items': ['git.index.add_all with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.worktree', 'connector.git.state', 'connector.git.commit.create']}]})

def info():
    return action(
        name="index.add_all",
        human=git_human(HUMAN, provide="No inputs are required; use only after deciding that every current worktree change belongs together.", result="Returns staged=true only after all current changes are staged. A block has no ready-to-commit result, and later worktree changes are outside this action."),
        effects=("stage all current worktree changes into the index",),
        outputs={"staged": "boolean"},
        failure_modes=("stage_blocked",),
        invalidates_observations=INDEX_INVALIDATION,
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
