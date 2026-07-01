"""git.worktrees probe."""

from __future__ import annotations

from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="worktrees",
        outputs={
            "count": "integer",
            "current_path": "string | null",
            "items": [
                {
                    "path": "string",
                    "head": "string",
                    "branch": "string | null",
                    "bare": "boolean",
                    "current": "boolean",
                    "detached": "boolean",
                }
            ],
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
            diagnostic_code="probe.git_worktrees.repo_root_missing",
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    command = ctx.command(
        ["git", "worktree", "list", "--porcelain"],
        failures={
            "os_error": "probe_failed",
            "nonzero": "probe_failed",
        },
    )

    parsed = _parse_worktrees_output(ctx, command.stdout, dict(command.raw), repository_root)
    if isinstance(parsed, OperationOutcome):
        return parsed

    items = parsed
    current_path = next((item["path"] for item in items if item["current"]), None)
    return ok(
        summary="Git worktree list inspected successfully",
        outputs={
            "count": len(items),
            "current_path": current_path,
            "items": items,
            "repository_root": repository_root,
        },
        raw=command.raw,
    )


def _parse_worktrees_output(
    ctx: OperationContext,
    stdout: str,
    raw: dict[str, object],
    repository_root: str,
) -> list[dict[str, object]] | OperationOutcome:
    items: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in stdout.splitlines():
        if not line:
            if current is None:
                continue
            validated = _finalize_entry(ctx, current, raw, repository_root)
            if isinstance(validated, OperationOutcome):
                return validated
            items.append(validated)
            current = None
            continue

        field, separator, value = line.partition(" ")
        if not separator:
            return _probe_failure(
                ctx,
                summary="Git worktree porcelain returned an invalid line",
                diagnostic_code="probe.git_worktrees.invalid_line",
                raw={"worktrees": raw, "line": line},
            )

        if field == "worktree":
            if current is not None:
                validated = _finalize_entry(ctx, current, raw, repository_root)
                if isinstance(validated, OperationOutcome):
                    return validated
                items.append(validated)
            current = {"path": value, "bare": False, "detached": False}
            continue

        if current is None:
            return _probe_failure(
                ctx,
                summary="Git worktree porcelain returned fields before a worktree header",
                diagnostic_code="probe.git_worktrees.invalid_line",
                raw={"worktrees": raw, "line": line},
            )

        if field == "HEAD":
            current["head"] = value
        elif field == "branch":
            prefix = "refs/heads/"
            if not value.startswith(prefix):
                return _probe_failure(
                    ctx,
                    summary="Git worktree porcelain returned an unsupported branch ref format",
                    diagnostic_code="probe.git_worktrees.invalid_branch_ref",
                    raw={"worktrees": raw, "line": line},
                )
            current["branch"] = value[len(prefix) :]
        elif field == "bare":
            current["bare"] = True
        elif field == "detached":
            current["detached"] = True
        elif field in {"locked", "prunable"}:
            continue
        else:
            return _probe_failure(
                ctx,
                summary="Git worktree porcelain returned an unexpected field",
                diagnostic_code="probe.git_worktrees.invalid_line",
                raw={"worktrees": raw, "line": line},
            )

    if current is not None:
        validated = _finalize_entry(ctx, current, raw, repository_root)
        if isinstance(validated, OperationOutcome):
            return validated
        items.append(validated)

    return items


def _finalize_entry(
    ctx: OperationContext,
    entry: dict[str, object],
    raw: dict[str, object],
    repository_root: str,
) -> dict[str, object] | OperationOutcome:
    path = entry.get("path")
    head = entry.get("head")
    branch = entry.get("branch")
    bare = bool(entry.get("bare", False))
    detached = bool(entry.get("detached", False))

    if not isinstance(path, str) or not path:
        return _probe_failure(
            ctx,
            summary="Git worktree porcelain omitted the worktree path",
            diagnostic_code="probe.git_worktrees.missing_path",
            raw={"worktrees": raw, "entry": dict(entry)},
        )
    if not isinstance(head, str) or not head:
        return _probe_failure(
            ctx,
            summary="Git worktree porcelain omitted the worktree head",
            diagnostic_code="probe.git_worktrees.missing_head",
            raw={"worktrees": raw, "entry": dict(entry)},
        )
    if branch is not None and (not isinstance(branch, str) or not branch):
        return _probe_failure(
            ctx,
            summary="Git worktree porcelain returned an empty branch value",
            diagnostic_code="probe.git_worktrees.invalid_branch_ref",
            raw={"worktrees": raw, "entry": dict(entry)},
        )
    if detached and branch is not None:
        return _probe_failure(
            ctx,
            summary="Git worktree porcelain returned both detached and branch state",
            diagnostic_code="probe.git_worktrees.inconsistent_entry",
            raw={"worktrees": raw, "entry": dict(entry)},
        )

    return {
        "path": path,
        "head": head,
        "branch": branch if isinstance(branch, str) else None,
        "bare": bare,
        "current": path == repository_root,
        "detached": detached,
    }


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
