"""git.worktree probe."""

from __future__ import annotations

from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="worktree",
        outputs={
            "clean": "boolean",
            "dirty_paths": ["string"],
            "has_untracked": "boolean",
            "has_staged_changes": "boolean",
            "has_unstaged_changes": "boolean",
            "repository_root": "string",
        },
        failure_modes=("probe_failed",),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    repository_root = ctx.bootstrap().context.get("repository_root")
    if not isinstance(repository_root, str) or not repository_root.strip():
        return _probe_failure(
            ctx,
            summary="Git bootstrap did not provide a usable repository root",
            diagnostic_code="probe.git_worktree.repo_root_missing",
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    command = ctx.command(
        ["git", "status", "--porcelain"],
        failures={
            "os_error": "probe_failed",
            "nonzero": "probe_failed",
        },
    )

    dirty_paths: list[str] = []
    has_untracked = False
    has_staged_changes = False
    has_unstaged_changes = False

    for line in command.stdout.splitlines():
        if not line:
            continue
        if len(line) < 4:
            return _probe_failure(
                ctx,
                summary="Git status porcelain returned a line that is too short to parse",
                diagnostic_code="probe.git_worktree.invalid_status_line",
                raw={"status": dict(command.raw), "line": line},
            )

        x = line[0]
        y = line[1]
        separator = line[2]
        path = line[3:]

        if separator != " ":
            return _probe_failure(
                ctx,
                summary="Git status porcelain returned an unexpected separator",
                diagnostic_code="probe.git_worktree.invalid_status_line",
                raw={"status": dict(command.raw), "line": line},
            )
        if not path:
            return _probe_failure(
                ctx,
                summary="Git status porcelain returned an entry without a path",
                diagnostic_code="probe.git_worktree.empty_path",
                raw={"status": dict(command.raw), "line": line},
            )

        if x == "?" and y == "?":
            has_untracked = True
            dirty_paths.append(path)
            continue
        if x == "!" and y == "!":
            continue
        if x != " ":
            has_staged_changes = True
        if y != " ":
            has_unstaged_changes = True
        if x != " " or y != " ":
            dirty_paths.append(path)

    return ok(
        summary="Git worktree inspected successfully",
        outputs={
            "clean": not dirty_paths,
            "dirty_paths": dirty_paths,
            "has_untracked": has_untracked,
            "has_staged_changes": has_staged_changes,
            "has_unstaged_changes": has_unstaged_changes,
            "repository_root": repository_root,
        },
        raw=command.raw,
    )


def _probe_failure(
    ctx: OperationContext,
    *,
    summary: str,
    diagnostic_code: str,
    raw: dict[str, object],
) -> OperationOutcome:
    return fail(
        code="probe_failed",
        summary=summary,
        diagnostics=(
            Diagnostic(
                code=diagnostic_code,
                level="error",
                message=summary,
                details={"reference": ctx.reference},
            ),
        ),
        raw=raw,
    )
