"""git.branches probe."""

from __future__ import annotations

from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="branches",
        outputs={
            "count": "integer",
            "current": "string | null",
            "items": [
                {
                    "name": "string",
                    "ref": "string",
                    "kind": "string",
                    "current": "boolean",
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
            diagnostic_code="probe.git_branches.repo_root_missing",
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    command = ctx.command(
        [
            "git",
            "branch",
            "--all",
            "--format=%(HEAD)%x09%(refname)%x09%(refname:short)",
        ],
        failures={
            "os_error": "probe_failed",
            "nonzero": "probe_failed",
        },
    )

    items: list[dict[str, object]] = []
    current_name: str | None = None

    for line in command.stdout.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            return _probe_failure(
                ctx,
                summary="Git branch inventory returned an unexpected line format",
                diagnostic_code="probe.git_branches.invalid_line",
                raw={"branches": dict(command.raw), "line": line},
            )
        head_marker, ref, short_name = parts
        if head_marker not in {"*", " "}:
            return _probe_failure(
                ctx,
                summary="Git branch inventory returned an unsupported current-branch marker",
                diagnostic_code="probe.git_branches.invalid_line",
                raw={"branches": dict(command.raw), "line": line},
            )
        if not ref or not short_name:
            return _probe_failure(
                ctx,
                summary="Git branch inventory returned an entry without a ref or short name",
                diagnostic_code="probe.git_branches.invalid_line",
                raw={"branches": dict(command.raw), "line": line},
            )

        kind = _classify_ref(ref)
        if kind is None:
            return _probe_failure(
                ctx,
                summary="Git branch inventory returned an unsupported ref kind",
                diagnostic_code="probe.git_branches.invalid_ref_kind",
                raw={"branches": dict(command.raw), "line": line, "ref": ref},
            )

        current = head_marker == "*"
        if current:
            if current_name is not None:
                return _probe_failure(
                    ctx,
                    summary="Git branch inventory reported more than one current branch",
                    diagnostic_code="probe.git_branches.multiple_current",
                    raw={"branches": dict(command.raw)},
                )
            current_name = short_name

        items.append(
            {
                "name": short_name,
                "ref": ref,
                "kind": kind,
                "current": current,
            }
        )

    return ok(
        summary="Git branch inventory inspected successfully",
        outputs={
            "count": len(items),
            "current": current_name,
            "items": items,
            "repository_root": repository_root,
        },
        raw=command.raw,
    )


def _classify_ref(ref: str) -> str | None:
    if ref.startswith("refs/heads/"):
        return "local"
    if ref.startswith("refs/remotes/"):
        return "remote"
    return None


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
