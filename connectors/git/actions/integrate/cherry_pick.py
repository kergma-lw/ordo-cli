"""git.integrate.cherry_pick action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git integrate cherry_pick',
 'goal': 'A workflow needs one targeted commit transplant such as backporting one fix without merging or rebasing the '
         'larger branch that originally contained it.',
 'summary': 'Apply one existing non-merge Git commit onto the current checkout as a new commit, without integrating '
            'the whole source ref history.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs one targeted commit transplant such as backporting one fix without merging '
                         'or rebasing the larger branch that originally contained it.',
                          'Use this for one chosen commit identity, not to integrate a whole ref '
                         'tip or replaying a branch range onto a new base.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the current checkout gains a new commit containing the selected commit\'s change, '
                         'and reports the resulting head revision.',
                         'Conflicts, unsupported merge commits, or other Git blocks do not produce a completed '
                         'transplant result.']},
              {'heading': 'Do not use for',
               'items': ['Integrating a whole branch tip or preserving branch topology; use '
                         'connector.git.integrate.merge or connector.git.integrate.merge_ff_only when the unit of '
                         'integration is one ref rather than one commit.',
                          'Cherry-picking merge commits or rewriting one topic branch onto a new base; this operation '
                         'rejects merge commits and is narrower than connector.git.integrate.rebase_onto.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.integrate.merge',
                               'summary': 'Sibling action for integrating a whole target ref instead of transplanting '
                                          'one selected commit'},
                              {'handle': 'connector.git.integrate.rebase_onto',
                               'summary': 'Sibling action for replaying a branch range onto a new base rather than '
                                          'copying one chosen commit'},
                              {'handle': 'connector.git.commits',
                                'summary': 'Read commit history before choosing which '
                                          'commit to cherry-pick'},
                              {'handle': 'connector.git.ref',
                                'summary': 'Resolve an exact ref when the workflow still needs to '
                                          'identify the source commit or source branch first'}]},
              {'heading': 'Examples', 'items': ['git.integrate.cherry_pick with inputs {"commit": "abc1234"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.commits',
                         'connector.git.integrate.merge',
                         'connector.git.integrate.rebase_onto']}]})

def info():
    return action(
        name="integrate.cherry_pick",
        human=git_human(HUMAN, provide="`commit`: required; provide the one non-merge commit to transplant.", result="Returns picked_commit, head_commit, and branch. A missing or merge commit, conflict, or other block does not produce a completed transplant; resolve conflicts before further integration."),
        inputs={"commit": "string"},
        effects=("apply a target commit onto the current checkout as a new commit",),
        outputs={"picked_commit": "string", "head_commit": "string", "branch": "string | null"},
        failure_modes=("commit_not_found", "merge_commit_not_supported", "cherry_pick_conflict", "cherry_pick_blocked"),
        invalidates_observations=COMMIT_GRAPH_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    commit_ref = str(ctx.input("commit"))
    branch = current_branch(ctx)
    if isinstance(branch, OperationOutcome):
        return branch

    picked_commit = require_commit(
        ctx,
        commit_ref,
        code="commit_not_found",
        summary=f"Commit '{commit_ref}' was not found",
        diagnostic_code="action.git.cherry_pick_not_found",
    )
    if isinstance(picked_commit, OperationOutcome):
        return picked_commit

    try:
        command = ctx.command(["git", "cherry-pick", commit_ref], failures={"os_error": "cherry_pick_blocked", "nonzero": "cherry_pick_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                (
                    "is a merge but no -m option was given",
                    "merge_commit_not_supported",
                    f"Commit '{commit_ref}' is a merge commit and is not supported by this cherry-pick action",
                    "action.git.cherry_pick_merge_commit_not_supported",
                ),
                ("after resolving the conflicts", "cherry_pick_conflict", f"Cherry-picking commit '{commit_ref}' produced conflicts", "action.git.cherry_pick_conflict"),
                ("could not apply", "cherry_pick_conflict", f"Cherry-picking commit '{commit_ref}' produced conflicts", "action.git.cherry_pick_conflict"),
            ),
            fallback_summary=f"Cherry-picking commit '{commit_ref}' failed",
        )

    merged_head = head_commit(ctx)
    if isinstance(merged_head, OperationOutcome):
        return merged_head

    return ok(
        summary=f"Cherry-picked commit '{commit_ref}'",
        outputs={"picked_commit": picked_commit, "head_commit": merged_head, "branch": branch},
        raw=command.raw,
    )
