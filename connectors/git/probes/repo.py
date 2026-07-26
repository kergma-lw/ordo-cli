"""git.repo probe."""

from __future__ import annotations

from pathlib import Path

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe


def info():
    return probe(
        name="repo",
        outputs={
            "exists": "boolean",
            "root": "string",
            "git_dir": "string",
            "inside_work_tree": "boolean",
            "bare": "boolean",
            "head_ref": "string | null",
            "worktree_path": "string | null",
            "common_dir": "string",
            "default_branch": "string | null",
        },
        failure_modes=("probe_failed",),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    bootstrap = ctx.bootstrap()
    root = bootstrap.context.get("repository_root")
    if not isinstance(root, str) or not root.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git bootstrap did not provide a usable repository root",
            diagnostic_code="probe.git_repo.bootstrap_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(bootstrap.context)},
        )

    raw_commands: dict[str, object] = {}

    git_dir = _required_text(
        ctx,
        label="git_dir",
        argv=("git", "rev-parse", "--absolute-git-dir"),
        raw_commands=raw_commands,
    )
    if isinstance(git_dir, OperationOutcome):
        return git_dir

    inside_work_tree = _required_bool(
        ctx,
        label="inside_work_tree",
        argv=("git", "rev-parse", "--is-inside-work-tree"),
        raw_commands=raw_commands,
    )
    if isinstance(inside_work_tree, OperationOutcome):
        return inside_work_tree

    bare = _required_bool(
        ctx,
        label="bare",
        argv=("git", "rev-parse", "--is-bare-repository"),
        raw_commands=raw_commands,
    )
    if isinstance(bare, OperationOutcome):
        return bare

    common_dir = _required_path(
        ctx,
        label="common_dir",
        argv=("git", "rev-parse", "--git-common-dir"),
        raw_commands=raw_commands,
    )
    if isinstance(common_dir, OperationOutcome):
        return common_dir

    head_ref = _optional_text(
        ctx,
        label="head_ref",
        argv=("git", "symbolic-ref", "--quiet", "--short", "HEAD"),
        raw_commands=raw_commands,
        allowed_returncodes=(1,),
    )
    if isinstance(head_ref, OperationOutcome):
        return head_ref

    default_branch = _optional_short_remote_branch(
        ctx,
        label="default_branch",
        argv=("git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"),
        raw_commands=raw_commands,
        allowed_returncodes=(1,),
    )
    if isinstance(default_branch, OperationOutcome):
        return default_branch

    worktree_path = None if bare else root

    return ok(
        summary="Git repository context inspected successfully",
        outputs={
            "exists": True,
            "root": root,
            "git_dir": git_dir,
            "inside_work_tree": inside_work_tree,
            "bare": bare,
            "head_ref": head_ref,
            "worktree_path": worktree_path,
            "common_dir": common_dir,
            "default_branch": default_branch,
        },
        raw={"commands": raw_commands},
    )


def _required_text(
    ctx: OperationContext,
    *,
    label: str,
    argv: tuple[str, ...],
    raw_commands: dict[str, object],
) -> str | OperationOutcome:
    try:
        command = ctx.command(argv, failures={"os_error": "probe_failed", "nonzero": "probe_failed"})
    except MappedOutcomeError as exc:
        return exc.outcome
    raw_commands[label] = command.raw
    value = command.stdout.strip()
    if not value:
        return fail_with_diagnostic(
            code="probe_failed",
            summary=f"Git command for '{label}' returned empty output",
            diagnostic_code="probe.git_repo.empty_required_field",
            reference=ctx.reference,
            raw={"commands": raw_commands},
        )
    return value


def _required_bool(
    ctx: OperationContext,
    *,
    label: str,
    argv: tuple[str, ...],
    raw_commands: dict[str, object],
) -> bool | OperationOutcome:
    value = _required_text(ctx, label=label, argv=argv, raw_commands=raw_commands)
    if isinstance(value, OperationOutcome):
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    return fail_with_diagnostic(
        code="probe_failed",
        summary=f"Git command for '{label}' returned unsupported boolean output",
        diagnostic_code="probe.git_repo.invalid_boolean",
        reference=ctx.reference,
        raw={"commands": raw_commands, "value": value},
    )


def _required_path(
    ctx: OperationContext,
    *,
    label: str,
    argv: tuple[str, ...],
    raw_commands: dict[str, object],
) -> str | OperationOutcome:
    value = _required_text(ctx, label=label, argv=argv, raw_commands=raw_commands)
    if isinstance(value, OperationOutcome):
        return value
    return _normalize_path(value)


def _optional_text(
    ctx: OperationContext,
    *,
    label: str,
    argv: tuple[str, ...],
    raw_commands: dict[str, object],
    allowed_returncodes: tuple[int, ...],
) -> str | None | OperationOutcome:
    try:
        command = ctx.command(argv, failures={"os_error": "probe_failed", "nonzero": "probe_failed"})
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if isinstance(returncode, int) and returncode in allowed_returncodes:
            raw_commands[label] = exc.outcome.raw
            return None
        return exc.outcome

    raw_commands[label] = command.raw
    value = command.stdout.strip()
    if not value:
        return fail_with_diagnostic(
            code="probe_failed",
            summary=f"Git command for '{label}' returned empty output",
            diagnostic_code="probe.git_repo.empty_optional_field",
            reference=ctx.reference,
            raw={"commands": raw_commands},
        )
    return value


def _optional_short_remote_branch(
    ctx: OperationContext,
    *,
    label: str,
    argv: tuple[str, ...],
    raw_commands: dict[str, object],
    allowed_returncodes: tuple[int, ...],
) -> str | None | OperationOutcome:
    value = _optional_text(
        ctx,
        label=label,
        argv=argv,
        raw_commands=raw_commands,
        allowed_returncodes=allowed_returncodes,
    )
    if isinstance(value, OperationOutcome) or value is None:
        return value
    if "/" not in value:
        return fail_with_diagnostic(
            code="probe_failed",
            summary=f"Git command for '{label}' returned unsupported remote HEAD format",
            diagnostic_code="probe.git_repo.invalid_remote_head",
            reference=ctx.reference,
            raw={"commands": raw_commands, "value": value},
        )
    return value.split("/", 1)[1]


def _normalize_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((Path.cwd() / path).resolve())
