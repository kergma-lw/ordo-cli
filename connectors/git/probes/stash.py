"""git.stash probe."""

from __future__ import annotations

from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="stash",
        outputs={
            "count": "integer",
            "items": [
                {
                    "name": "string",
                    "selector": "string",
                    "summary": "string",
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
            diagnostic_code="probe.git_stash.repo_root_missing",
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    command = ctx.command(
        ["git", "stash", "list"],
        failures={
            "os_error": "probe_failed",
            "nonzero": "probe_failed",
        },
    )

    items: list[dict[str, str]] = []
    for line in command.stdout.splitlines():
        if not line:
            continue
        selector, separator, summary = line.partition(": ")
        if not separator:
            return _probe_failure(
                ctx,
                summary="Git stash list returned a line with an unsupported format",
                diagnostic_code="probe.git_stash.invalid_line",
                raw={"stash": dict(command.raw), "line": line},
            )
        if not selector.startswith("stash@{") or not selector.endswith("}"):
            return _probe_failure(
                ctx,
                summary="Git stash list returned an invalid stash selector",
                diagnostic_code="probe.git_stash.invalid_selector",
                raw={"stash": dict(command.raw), "line": line},
            )
        if not summary:
            return _probe_failure(
                ctx,
                summary="Git stash list returned an entry without a summary",
                diagnostic_code="probe.git_stash.empty_summary",
                raw={"stash": dict(command.raw), "line": line},
            )
        items.append({"name": selector, "selector": selector, "summary": summary})

    return ok(
        summary="Git stash list inspected successfully",
        outputs={
            "count": len(items),
            "items": items,
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
