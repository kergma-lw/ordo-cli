"""git.integrate.merge action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git integrate merge',
 'goal': 'A workflow intentionally wants one merge commit that preserves the integration event instead of silently '
         'linearizing history.',
 'summary': 'Integrate one target Git ref into the current checkout by creating a merge commit with ordinary merge '
            'semantics, even when a fast-forward would have been possible.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow intentionally wants one merge commit that preserves the integration event instead '
                         'of silently linearizing history.',
                         'The integration target is one ref such as feature/demo or origin/main, not one standalone '
                         'commit transplant or one branch-range rewrite.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the current checkout contains the target ref and points to the resulting head '
                         'revision.',
                         'If Git finds conflicts or blocks the merge, the action does not report the target as '
                         'integrated.']},
              {'heading': 'Do not use for',
               'items': ['Requiring a linear-history-only fast-forward update; use '
                         'connector.git.integrate.merge_ff_only when creating a merge commit would be the wrong '
                         'outcome.',
                         'Replaying one commit or rewriting a topic branch onto a new base; use '
                         'connector.git.integrate.cherry_pick or connector.git.integrate.rebase_onto for those '
                         'narrower rewrite semantics.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.integrate.merge_ff_only',
                               'summary': 'Sibling action for integrating one target ref only when the current '
                                          'checkout can fast-forward without creating a merge commit'},
                              {'handle': 'connector.git.integrate.cherry_pick',
                               'summary': 'Sibling action for copying one commit onto the current checkout without '
                                          'merging a whole target ref'},
                              {'handle': 'connector.git.integrate.rebase_onto',
                               'summary': 'Sibling action for rewriting one branch range onto a new base instead of '
                                          'integrating into the current checkout by merge'},
                              {'handle': 'connector.git.range',
                                'summary': 'Compare ahead/behind or merge-base facts before choosing '
                                          'an integration strategy'}]},
              {'heading': 'Examples', 'items': ['git.integrate.merge with inputs {"ref": "feature/demo"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.integrate.merge_ff_only',
                         'connector.git.range',
                         'connector.git.integrate.cherry_pick']}]})

def info():
    return action(
        name="integrate.merge",
        human=git_human(HUMAN, provide="`ref`: required; provide the target revision to integrate. Confirm that creating an integration commit is the intended history policy before merging it into the current checkout.", result="Returns merged_ref, head_commit, and branch after creating the integration commit. A missing ref, conflict, or block does not report integration; choose merge_ff_only when an explicit merge commit is unacceptable."),
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
