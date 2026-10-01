"""git.integrate.merge_ff_only action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git integrate merge_ff_only',
 'goal': 'A workflow wants linear-history integration and should fail cleanly rather than synthesize a merge commit '
         'for the target ref.',
 'summary': 'Integrate one target Git ref into the current checkout only if the update can fast-forward, refusing to '
            'create a merge commit when histories have diverged.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow wants linear-history integration and should fail cleanly rather than synthesize a '
                         'merge commit for the target ref.',
                          'Use this specifically to advance the current checkout to one descendant '
                         'ref, not about copying one commit or rewriting a topic branch range.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the current checkout advances to the target ref without creating a merge commit.',
                         'When the histories cannot fast-forward, or Git otherwise blocks the update, the action does '
                         'not report an integration result.']},
              {'heading': 'Do not use for',
               'items': ['Preserving an explicit integration commit even when fast-forward would be possible; use '
                         'connector.git.integrate.merge for ordinary merge semantics.',
                         'Branch-range rewrites or single-commit transplants; use connector.git.integrate.rebase_onto '
                          'or connector.git.integrate.cherry_pick for those rewrite-oriented operations.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.integrate.merge',
                               'summary': 'Sibling action for integrating the same target ref through an explicit '
                                          'merge commit instead of fast-forward-only admission'},
                              {'handle': 'connector.git.range',
                                'summary': 'Compare two endpoints to confirm whether they are already in a '
                                          'fast-forward relationship before this action runs'},
                              {'handle': 'connector.git.upstream',
                                'summary': 'Read current-branch upstream context when the workflow first '
                                          'needs to choose which target ref should fast-forward'},
                              {'handle': 'connector.git.integrate.rebase_onto',
                               'summary': 'Sibling action for rewriting branch history when linear movement requires '
                                          'replay rather than pure fast-forward integration'}]},
              {'heading': 'Examples', 'items': ['git.integrate.merge_ff_only with inputs {"ref": "origin/main"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.range', 'connector.git.integrate.merge', 'connector.git.upstream']}]})

def info():
    return action(
        name="integrate.merge_ff_only",
        human=git_human(HUMAN, provide="`ref`: required; provide the target revision to integrate. Use this only after confirming the current checkout can advance without creating an integration commit.", result="Returns merged_ref, head_commit, and branch only after the current checkout advances without a merge commit. A missing ref, non-fast-forward relationship, or block leaves no integration result; use merge when an explicit merge commit is intended."),
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
