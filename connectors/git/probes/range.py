"""git.range probe."""

from __future__ import annotations

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="range",
        inputs={"base": "string", "head": "string"},
        outputs={
            "base": "string",
            "head": "string",
            "base_oid": "string",
            "head_oid": "string",
            "merge_base_oid": "string | null",
            "ahead_count": "integer",
            "behind_count": "integer",
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
            diagnostic_code="probe.git_range.repo_root_missing",
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    base = ctx.input("base")
    head = ctx.input("head")
    if not isinstance(base, str) or not base.strip() or not isinstance(head, str) or not head.strip():
        return _probe_failure(
            ctx,
            summary="git.range requires non-empty base and head inputs",
            diagnostic_code="probe.git_range.invalid_input",
            raw={"base": base, "head": head},
        )

    raw: dict[str, object] = {}

    base_oid = _resolve_oid(ctx, ref_name=base, label="base", raw=raw)
    if isinstance(base_oid, OperationOutcome):
        return base_oid
    head_oid = _resolve_oid(ctx, ref_name=head, label="head", raw=raw)
    if isinstance(head_oid, OperationOutcome):
        return head_oid

    merge_base_oid = _resolve_merge_base(ctx, base=base, head=head, raw=raw)
    if isinstance(merge_base_oid, OperationOutcome):
        return merge_base_oid

    counts = _resolve_counts(ctx, base=base, head=head, raw=raw)
    if isinstance(counts, OperationOutcome):
        return counts
    ahead_count, behind_count = counts

    return ok(
        summary="Git range facts inspected successfully",
        outputs={
            "base": base,
            "head": head,
            "base_oid": base_oid,
            "head_oid": head_oid,
            "merge_base_oid": merge_base_oid,
            "ahead_count": ahead_count,
            "behind_count": behind_count,
            "repository_root": repository_root,
        },
        raw=raw,
    )


def _resolve_oid(
    ctx: OperationContext,
    *,
    ref_name: str,
    label: str,
    raw: dict[str, object],
) -> str | OperationOutcome:
    try:
        command = ctx.command(
            ["git", "rev-parse", "--verify", "--end-of-options", f"{ref_name}^{{object}}"],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 128:
            return _probe_failure(
                ctx,
                summary=f"Git could not resolve {label} ref '{ref_name}'",
                diagnostic_code="probe.git_range.unresolved_ref",
                raw={**raw, label: dict(exc.outcome.raw), "ref": ref_name},
            )
        return exc.outcome
    raw[label] = dict(command.raw)
    oid = command.stdout.strip()
    if not oid:
        return _probe_failure(
            ctx,
            summary=f"Git returned an empty oid for {label} ref '{ref_name}'",
            diagnostic_code="probe.git_range.empty_oid",
            raw={**raw, "ref": ref_name},
        )
    return oid


def _resolve_merge_base(
    ctx: OperationContext,
    *,
    base: str,
    head: str,
    raw: dict[str, object],
) -> str | None | OperationOutcome:
    try:
        command = ctx.command(
            ["git", "merge-base", base, head],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 1:
            raw["merge_base"] = dict(exc.outcome.raw)
            return None
        return exc.outcome
    raw["merge_base"] = dict(command.raw)
    merge_base_oid = command.stdout.strip()
    if not merge_base_oid:
        return _probe_failure(
            ctx,
            summary="Git merge-base returned empty output",
            diagnostic_code="probe.git_range.empty_merge_base",
            raw=raw,
        )
    return merge_base_oid


def _resolve_counts(
    ctx: OperationContext,
    *,
    base: str,
    head: str,
    raw: dict[str, object],
) -> tuple[int, int] | OperationOutcome:
    command = ctx.command(
        ["git", "rev-list", "--left-right", "--count", f"{base}...{head}"],
        failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
    )
    raw["counts"] = dict(command.raw)
    parts = command.stdout.strip().split()
    if len(parts) != 2:
        return _probe_failure(
            ctx,
            summary="Git rev-list returned an unexpected ahead/behind count format",
            diagnostic_code="probe.git_range.invalid_counts",
            raw=raw,
        )
    try:
        behind_count = int(parts[0])
        ahead_count = int(parts[1])
    except ValueError:
        return _probe_failure(
            ctx,
            summary="Git rev-list returned non-integer ahead/behind counts",
            diagnostic_code="probe.git_range.invalid_counts",
            raw=raw,
        )
    if behind_count < 0 or ahead_count < 0:
        return _probe_failure(
            ctx,
            summary="Git rev-list returned negative ahead/behind counts",
            diagnostic_code="probe.git_range.invalid_counts",
            raw=raw,
        )
    return ahead_count, behind_count


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
