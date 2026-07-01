"""git.ref probe."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe


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
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git bootstrap did not provide a usable repository root",
            diagnostic_code="probe.git_ref.repo_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    ref_name = ctx.input("ref")
    if not isinstance(ref_name, str) or not ref_name.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.ref requires a non-empty ref input",
            diagnostic_code="probe.git_ref.invalid_input",
            reference=ctx.reference,
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
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git rev-parse returned an empty oid for an existing ref",
            diagnostic_code="probe.git_ref.empty_oid",
            reference=ctx.reference,
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
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git symbolic-ref returned empty output for a symbolic ref",
                diagnostic_code="probe.git_ref.empty_symbolic_target",
                reference=ctx.reference,
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

