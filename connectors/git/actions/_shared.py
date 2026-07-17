"""Shared helpers for git action handlers."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic


BRANCH_INVENTORY_INVALIDATION: tuple[str, ...] = ("git.branches", "git.ref.*")
CHECKOUT_STATE_INVALIDATION: tuple[str, ...] = (
    "git.branch",
    "git.branches",
    "git.upstream",
    "git.ref.*",
    "git.worktree",
    "git.worktrees",
    "git.state",
    "git.repo",
    "git.range",
    "git.commits",
)
FETCH_INVALIDATION: tuple[str, ...] = (
    "git.ref.*",
    "git.branches",
    "git.repo",
    "git.range",
    "git.commits",
)
INDEX_INVALIDATION: tuple[str, ...] = ("git.worktree", "git.state")
COMMIT_GRAPH_INVALIDATION: tuple[str, ...] = (
    "git.ref.*",
    "git.worktree",
    "git.worktrees",
    "git.state",
    "git.range",
    "git.commits",
)


def current_branch(ctx: OperationContext) -> str | None | OperationOutcome:
    outcome = ctx.call("branch")
    if outcome.status != "ok":
        return outcome
    value = outcome.outputs.get("value")
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value
    return fail_with_diagnostic(
        code="action_failed",
        summary="git.branch returned an unusable branch value",
        diagnostic_code="action.git.invalid_branch_probe_output",
        reference=ctx.reference,
        raw={"branch": dict(outcome.raw)},
    )


def require_branch_name(ctx: OperationContext, branch: str) -> OperationOutcome | None:
    return _run_expect_ok(
        ctx,
        ["git", "check-ref-format", "--branch", branch],
        code="invalid_branch",
        summary=f"Branch '{branch}' is not a valid branch name",
        diagnostic_code="action.git.invalid_branch",
    )


def require_local_branch(ctx: OperationContext, branch: str, *, code: str = "branch_not_found") -> OperationOutcome | None:
    return _run_expect_ok(
        ctx,
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        code=code,
        summary=f"Local branch '{branch}' was not found",
        diagnostic_code="action.git.branch_not_found",
    )


def require_commit(ctx: OperationContext, ref: str, *, code: str, summary: str, diagnostic_code: str) -> str | OperationOutcome:
    try:
        command = ctx.command(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            failures={"os_error": "action_failed", "nonzero": code},
        )
    except MappedOutcomeError as exc:
        return fail_with_diagnostic(
            code=code,
            summary=summary,
            diagnostic_code=diagnostic_code,
            reference=ctx.reference,
            raw=exc.outcome.raw,
        )
    value = command.stdout.strip()
    if not value:
        return fail_with_diagnostic(
            code=code,
            summary=summary,
            diagnostic_code=diagnostic_code,
            reference=ctx.reference,
            raw=command.raw,
        )
    return value


def head_commit(ctx: OperationContext) -> str | OperationOutcome:
    return require_commit(
        ctx,
        "HEAD",
        code="action_failed",
        summary="HEAD could not be resolved to a commit",
        diagnostic_code="action.git.head_unresolved",
    )


def map_nonzero(
    ctx: OperationContext,
    exc: MappedOutcomeError,
    *,
    cases: tuple[tuple[str, str, str, str], ...],
    fallback_summary: str,
) -> OperationOutcome:
    text = _error_text(exc.outcome)
    for needle, code, summary, diagnostic_code in cases:
        if needle in text:
            return fail_with_diagnostic(
                code=code,
                summary=summary,
                diagnostic_code=diagnostic_code,
                reference=ctx.reference,
                raw=exc.outcome.raw,
            )
    return fail_with_diagnostic(
        code="action_failed",
        summary=fallback_summary,
        diagnostic_code="action.git.command_failed",
        reference=ctx.reference,
        raw=exc.outcome.raw,
    )


def _run_expect_ok(
    ctx: OperationContext,
    argv: list[str],
    *,
    code: str,
    summary: str,
    diagnostic_code: str,
) -> OperationOutcome | None:
    try:
        ctx.command(argv, failures={"os_error": "action_failed", "nonzero": code})
    except MappedOutcomeError as exc:
        return fail_with_diagnostic(
            code=code,
            summary=summary,
            diagnostic_code=diagnostic_code,
            reference=ctx.reference,
            raw=exc.outcome.raw,
        )
    return None


def _error_text(outcome: OperationOutcome) -> str:
    stdout = outcome.raw.get("stdout")
    stderr = outcome.raw.get("stderr")
    text = ""
    if isinstance(stdout, str):
        text += stdout
    if isinstance(stderr, str):
        text += f"\n{stderr}"
    return text.lower()
