"""git.integrate.rebase_onto action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero, require_commit
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git integrate rebase_onto',
 'goal': 'A workflow needs to move a topic branch onto a new base while preserving only the branch-local commit range '
         'after one upstream split point.',
 'summary': 'Rewrite one non-default Git branch by replaying the commits after one upstream boundary onto a new base '
            'with rebase --onto semantics.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to move a topic branch onto a new base while preserving only the '
                          'branch-local commit range after one upstream split point.',
                          'Use this for branch-range rewriting, not whole-ref integration into the '
                          'current checkout and not a one-commit transplant.']},
              {'heading': 'What to provide',
               'items': ['Provide the branch to rewrite, the upstream boundary after which its commits are selected, '
                         'and the new base to replay them onto.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the branch points to its newly rebased head revision.',
                         'If replay produces conflicts or Git cannot begin or finish the rebase, the rewrite is blocked '
                         'rather than reported as complete.']},
              {'heading': 'Do not use for',
               'items': ['Integrating a target ref into the current checkout without rewriting branch history; use '
                         'connector.git.integrate.merge or connector.git.integrate.merge_ff_only for those integration '
                         'semantics.',
                          'Rebasing the repository default branch or copying only one selected commit; this operation '
                         'protects the default branch and is broader than connector.git.integrate.cherry_pick.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.integrate.merge',
                               'summary': 'Sibling action for integrating by merge instead of rewriting one branch '
                                          'range onto a new base'},
                              {'handle': 'connector.git.integrate.cherry_pick',
                               'summary': 'Sibling action for replaying one chosen commit instead of rebasing an '
                                          'entire branch-local range'},
                              {'handle': 'connector.git.range',
                                'summary': 'Compare base/head relationships before choosing onto '
                                          'and upstream boundaries'},
                              {'handle': 'connector.git.branch',
                                'summary': 'Read current checkout branch identity when the workflow first '
                                          'needs to confirm which branch is being rewritten'}]},
              {'heading': 'Examples',
               'items': ['git.integrate.rebase_onto with inputs {"branch": "feature/demo", "onto": "origin/main", '
                         '"upstream": "main"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.range', 'connector.git.branch', 'connector.git.integrate.cherry_pick']}]})

def info():
    return action(
        name="integrate.rebase_onto",
        human=git_human(HUMAN, provide="`branch`: required; provide the branch to rewrite. `upstream`: required; provide the upstream boundary. `onto`: required; provide the new base.", result="Checks out (switches to) `branch` before replaying it, then returns branch, onto, and head_commit after replay as the newly rebased head revision. Missing references, protected default branch, conflicts, or blocks do not report a completed rewrite; resolve conflicts before later history actions."),
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
