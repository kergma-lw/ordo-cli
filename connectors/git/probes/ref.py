"""git.ref probe."""

from __future__ import annotations

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="ref",
        inputs={"ref": "string"},
        outputs={
            "name": "string",
            "exists": "boolean",
            "oid": "string | null",
            "symbolic": "boolean",
            "symbolic_target": "string | null",
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
            diagnostic_code="probe.git_ref.repo_root_missing",
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    ref_name = ctx.input("ref")
    if not isinstance(ref_name, str) or not ref_name.strip():
        return _probe_failure(
            ctx,
            summary="git.ref requires a non-empty ref input",
            diagnostic_code="probe.git_ref.invalid_input",
            raw={"ref": ref_name},
        )

    raw: dict[str, object] = {}

    try:
        oid_command = ctx.command(
            ["git", "rev-parse", "--verify", "--end-of-options", f"{ref_name}^{{object}}"],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 128:
            raw["oid"] = dict(exc.outcome.raw)
            return ok(
                summary="Git ref inspected successfully",
                outputs={
                    "name": ref_name,
                    "exists": False,
                    "oid": None,
                    "symbolic": False,
                    "symbolic_target": None,
                    "repository_root": repository_root,
                },
                raw=raw,
            )
        return exc.outcome

    raw["oid"] = dict(oid_command.raw)
    oid = oid_command.stdout.strip()
    if not oid:
        return _probe_failure(
            ctx,
            summary="Git rev-parse returned an empty oid for an existing ref",
            diagnostic_code="probe.git_ref.empty_oid",
            raw=raw,
        )

    symbolic = False
    symbolic_target: str | None = None
    try:
        symbolic_command = ctx.command(
            ["git", "symbolic-ref", "--quiet", ref_name],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 1:
            raw["symbolic"] = dict(exc.outcome.raw)
        else:
            return exc.outcome
    else:
        raw["symbolic"] = dict(symbolic_command.raw)
        symbolic_target = symbolic_command.stdout.strip()
        if not symbolic_target:
            return _probe_failure(
                ctx,
                summary="Git symbolic-ref returned empty output for a symbolic ref",
                diagnostic_code="probe.git_ref.empty_symbolic_target",
                raw=raw,
            )
        symbolic = True

    return ok(
        summary="Git ref inspected successfully",
        outputs={
            "name": ref_name,
            "exists": True,
            "oid": oid,
            "symbolic": symbolic,
            "symbolic_target": symbolic_target,
            "repository_root": repository_root,
        },
        raw=raw,
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
