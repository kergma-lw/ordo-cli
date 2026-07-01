"""git.state probe."""

from __future__ import annotations

from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe


def info():
    return probe(
        name="state",
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
