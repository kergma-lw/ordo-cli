"""git.state probe."""

from __future__ import annotations

from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git state',
 'goal': 'A workflow needs one compact readiness snapshot before deciding whether committing, switching, syncing, or '
         'publishing repository state makes sense.',
  'summary': 'Read one combined Git repository-state snapshot from current-branch context, worktree '
             'cleanliness flags, and stash count.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs one compact readiness snapshot before deciding whether committing, '
                         'switching, syncing, or publishing repository state makes sense.',
                         'Later logic needs branch, detached, worktree-cleanliness, and stash-count facts together '
                         'rather than one path-level worktree inventory alone.']},
              {'heading': 'Do not use for',
               'items': ['Inspecting the exact dirty path list or keeping staged-versus-unstaged file paths visible; '
                          'use connector.git.worktree for that narrower path-level check.',
                         'Listing stash entries themselves or mutating staging state; use connector.git.stash for '
                         'stash inventory and connector.git.index.add_all for full-worktree staging.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.worktree',
                                'summary': 'Read path-level worktree details instead of one combined '
                                          'repository snapshot'},
                              {'handle': 'connector.git.branch',
                                'summary': 'Read only the current checkout branch when broader cleanliness '
                                          'and stash context are unnecessary'},
                              {'handle': 'connector.git.stash',
                                'summary': 'List stash entries instead of only the stash '
                                          'count summary'},
                              {'handle': 'connector.git.index.add_all',
                               'summary': 'Sibling action for staging the whole current worktree after this summary '
                                          'confirms the repository is ready'}]},
              {'heading': 'Examples', 'items': ['git.state with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.worktree', 'connector.git.index.add_all', 'connector.git.branch']}]})

def info():
    return probe(
        name="state",
        human=git_human(HUMAN, provide="No inputs are required; run from the checkout whose readiness the workflow must decide.", result="Returns branch, detached, worktree_clean, has_untracked, has_staged_changes, has_unstaged_changes, stash_count, and repository_root. It combines point-in-time observations, so a later action must not assume they remain unchanged."),
        outputs={
            "branch": "string | null",
            "detached": "boolean",
            "worktree_clean": "boolean",
            "has_untracked": "boolean",
            "has_staged_changes": "boolean",
            "has_unstaged_changes": "boolean",
            "stash_count": "integer",
            "repository_root": "string",
        },
        failure_modes=("probe_failed",),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    outputs: dict[str, object] = {}
    raw: dict[str, object] = {}

    branch_outcome = ctx.call("branch")
    if branch_outcome.status != "ok":
        return branch_outcome

    worktree_outcome = ctx.call("worktree")
    if worktree_outcome.status != "ok":
        return worktree_outcome

    stash_outcome = ctx.call("stash")
    if stash_outcome.status != "ok":
        return stash_outcome

    raw["branch"] = dict(branch_outcome.raw)
    raw["worktree"] = dict(worktree_outcome.raw)
    raw["stash"] = dict(stash_outcome.raw)

    collision = _set_output(outputs, "branch", branch_outcome.outputs.get("value"))
    if collision is not None:
        return _collision_failure(ctx, collision, raw)
    collision = _set_output(outputs, "detached", branch_outcome.outputs.get("detached"))
    if collision is not None:
        return _collision_failure(ctx, collision, raw)
    collision = _set_output(outputs, "repository_root", branch_outcome.outputs.get("repository_root"))
    if collision is not None:
        return _collision_failure(ctx, collision, raw)

    collision = _set_output(outputs, "worktree_clean", worktree_outcome.outputs.get("clean"))
    if collision is not None:
        return _collision_failure(ctx, collision, raw)
    collision = _set_output(outputs, "has_untracked", worktree_outcome.outputs.get("has_untracked"))
    if collision is not None:
        return _collision_failure(ctx, collision, raw)
    collision = _set_output(outputs, "has_staged_changes", worktree_outcome.outputs.get("has_staged_changes"))
    if collision is not None:
        return _collision_failure(ctx, collision, raw)
    collision = _set_output(outputs, "has_unstaged_changes", worktree_outcome.outputs.get("has_unstaged_changes"))
    if collision is not None:
        return _collision_failure(ctx, collision, raw)

    worktree_root = worktree_outcome.outputs.get("repository_root")
    branch_root = outputs.get("repository_root")
    if worktree_root != branch_root:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.branch and git.worktree reported different repository roots",
            diagnostic_code="probe.git_state.inconsistent_repository_root",
            reference=ctx.reference,
            raw=raw,
        )

    collision = _set_output(outputs, "stash_count", stash_outcome.outputs.get("count"))
    if collision is not None:
        return _collision_failure(ctx, collision, raw)

    stash_root = stash_outcome.outputs.get("repository_root")
    if stash_root != branch_root:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.branch and git.stash reported different repository roots",
            diagnostic_code="probe.git_state.inconsistent_repository_root",
            reference=ctx.reference,
            raw=raw,
        )

    return ok(
        summary="Git repository state inspected successfully",
        outputs=outputs,
        raw=raw,
    )


def _set_output(outputs: dict[str, object], key: str, value: object) -> str | None:
    if key in outputs:
        return key
    outputs[key] = value
    return None


def _collision_failure(ctx: OperationContext, key: str, raw: dict[str, object]) -> OperationOutcome:
    return fail_with_diagnostic(
        code="probe_failed",
        summary=f"Field collision while assembling git.state outputs: {key}",
        diagnostic_code="probe.git_state.field_collision",
        reference=ctx.reference,
        raw=raw,
    )
