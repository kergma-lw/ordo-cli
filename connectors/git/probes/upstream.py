"""git.upstream probe."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe


def info():
    return probe(
        name="upstream",
        outputs={
            "configured": "boolean",
            "branch": "string | null",
            "upstream_ref": "string | null",
            "remote": "string | null",
            "remote_branch": "string | null",
            "repository_root": "string",
        },
        failure_modes=("probe_failed",),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch_outcome = ctx.call("branch")
    if branch_outcome.status != "ok":
        return branch_outcome

    repository_root = branch_outcome.outputs.get("repository_root")
    if not isinstance(repository_root, str) or not repository_root.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.branch did not provide a usable repository root",
            diagnostic_code="probe.git_upstream.repo_root_missing",
            reference=ctx.reference,
            raw={"branch": dict(branch_outcome.raw)},
        )

    branch = branch_outcome.outputs.get("value")
    detached = branch_outcome.outputs.get("detached")
    if detached is True:
        return ok(
            summary="Git upstream relationship inspected successfully",
            outputs={
                "configured": False,
                "branch": None,
                "upstream_ref": None,
                "remote": None,
                "remote_branch": None,
                "repository_root": repository_root,
            },
            raw={"branch": dict(branch_outcome.raw)},
        )
    if not isinstance(branch, str) or not branch:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.branch returned an unusable branch name for upstream inspection",
            diagnostic_code="probe.git_upstream.invalid_branch",
            reference=ctx.reference,
            raw={"branch": dict(branch_outcome.raw)},
        )

    try:
        command = ctx.command(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 128:
            return ok(
                summary="Git upstream relationship inspected successfully",
                outputs={
                    "configured": False,
                    "branch": branch,
                    "upstream_ref": None,
                    "remote": None,
                    "remote_branch": None,
                    "repository_root": repository_root,
                },
                raw={"branch": dict(branch_outcome.raw), "upstream": dict(exc.outcome.raw)},
            )
        return exc.outcome

    upstream_ref = command.stdout.strip()
    if not upstream_ref:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git upstream command returned empty output",
            diagnostic_code="probe.git_upstream.empty_ref",
            reference=ctx.reference,
            raw={"branch": dict(branch_outcome.raw), "upstream": dict(command.raw)},
        )

    remote, remote_branch = _split_upstream_ref(upstream_ref)
    if remote is None or remote_branch is None:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git upstream command returned an unsupported upstream ref format",
            diagnostic_code="probe.git_upstream.invalid_ref",
            reference=ctx.reference,
            raw={"branch": dict(branch_outcome.raw), "upstream": dict(command.raw), "ref": upstream_ref},
        )

    return ok(
        summary="Git upstream relationship inspected successfully",
        outputs={
            "configured": True,
            "branch": branch,
            "upstream_ref": upstream_ref,
            "remote": remote,
            "remote_branch": remote_branch,
            "repository_root": repository_root,
        },
        raw={"branch": dict(branch_outcome.raw), "upstream": dict(command.raw)},
    )


def _split_upstream_ref(upstream_ref: str) -> tuple[str | None, str | None]:
    prefix = "refs/remotes/"
    if upstream_ref.startswith(prefix):
        remainder = upstream_ref[len(prefix) :]
    else:
        remainder = upstream_ref
    if "/" not in remainder:
        return None, None
    remote, remote_branch = remainder.split("/", 1)
    if not remote or not remote_branch:
        return None, None
    return remote, remote_branch

