"""git.branch probe."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe


def info():
    return probe(
        name="branch",
        outputs={
            "value": "string | null",
            "ref": "string | null",
            "detached": "boolean",
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
            diagnostic_code="probe.git_branch.repo_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    try:
        command = ctx.command(
            ["git", "symbolic-ref", "--quiet", "HEAD"],
            failures={
                "os_error": "probe_failed",
                "nonzero": "probe_failed",
            },
        )
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 1:
            return ok(
                summary="Current branch context inspected successfully",
                outputs={
                    "value": None,
                    "ref": None,
                    "detached": True,
                    "repository_root": repository_root,
                },
                raw={"branch": dict(exc.outcome.raw)},
            )
        return exc.outcome

    ref = command.stdout.strip()
    if not ref:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git symbolic-ref returned empty output",
            diagnostic_code="probe.git_branch.empty_ref",
            reference=ctx.reference,
            raw={"branch": dict(command.raw)},
        )
    prefix = "refs/heads/"
    if not ref.startswith(prefix):
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git symbolic-ref returned unsupported ref format",
            diagnostic_code="probe.git_branch.invalid_ref",
            reference=ctx.reference,
            raw={"branch": dict(command.raw), "ref": ref},
        )
    branch = ref[len(prefix) :]
    if not branch:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git symbolic-ref returned an empty branch name",
            diagnostic_code="probe.git_branch.empty_name",
            reference=ctx.reference,
            raw={"branch": dict(command.raw), "ref": ref},
        )
    return ok(
        summary="Current branch context inspected successfully",
        outputs={"value": branch, "ref": ref, "detached": False, "repository_root": repository_root},
        raw={"branch": dict(command.raw)},
    )
