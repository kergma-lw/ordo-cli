"""git.commits probe."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_external_command, fail_with_diagnostic, ok, probe

_FIELD_SEPARATOR = "\x1f"
_RECORD_SEPARATOR = "\x1e"


def info():
    return probe(
        name="commits",
        summary=(
            "Return a bounded readable list of commit texts from one revision scope with only minimal metadata. "
            "This probe is intentionally narrow: it does not expose patch text, changed files, diff stats, graph decoration, or arbitrary git log formatting."
        ),
        inputs={"limit": "integer", "rev": "string"},
        outputs={
            "count": "integer",
            "rev": "string",
            "items": [
                {
                    "commit": "string",
                    "subject": "string",
                    "body": "string",
                    "text": "string",
                    "author_name": "string",
                    "committed_at": "string",
                }
            ],
            "repository_root": "string",
        },
        failure_modes=("probe_failed",),
        examples=(
            {"reference": "git.commits", "inputs": {"limit": 5, "rev": "HEAD"}},
            {"reference": "git.commits", "inputs": {"limit": 3, "rev": "HEAD~10..HEAD"}},
        ),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    repository_root = ctx.bootstrap().context.get("repository_root")
    if not isinstance(repository_root, str) or not repository_root.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git bootstrap did not provide a usable repository root",
            diagnostic_code="probe.git_commits.repo_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    limit = ctx.input("limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.commits requires a positive integer limit",
            diagnostic_code="probe.git_commits.invalid_limit",
            reference=ctx.reference,
            raw={"limit": limit},
        )

    rev_input = ctx.input("rev")
    if isinstance(rev_input, str) and rev_input.strip():
        rev = rev_input.strip()
    else:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.commits requires rev to be a non-empty string",
            diagnostic_code="probe.git_commits.invalid_rev",
            reference=ctx.reference,
            raw={"rev": rev_input},
        )

    command_argv = [
        "git",
        "log",
        "--no-show-signature",
        f"--max-count={limit}",
        f"--format=%H%x1f%an%x1f%cI%x1f%s%x1f%b%x1e",
        rev,
    ]

    try:
        command = ctx.command(command_argv, failures={"os_error": "probe_failed", "nonzero": "probe_failed"})
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 128:
            return fail_with_diagnostic(
                code="probe_failed",
                summary=f"Git could not resolve revision scope '{rev}'",
                diagnostic_code="probe.git_commits.unresolved_rev",
                reference=ctx.reference,
                raw={"rev": rev, "log": dict(exc.outcome.raw)},
            )
        return fail_external_command(
            code="probe_failed",
            summary="Git commit log inspection failed",
            diagnostic_code="probe.git_commits.command_failed",
            reference=ctx.reference,
            details={"rev": rev},
            raw=exc.outcome.raw,
            tool="git",
        )

    items: list[dict[str, object]] = []
    for raw_record in command.stdout.split(_RECORD_SEPARATOR):
        if not raw_record:
            continue
        record = raw_record.rstrip("\n")
        if not record:
            continue
        parts = record.split(_FIELD_SEPARATOR)
        if len(parts) != 5:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git log returned an unexpected commit entry format",
                diagnostic_code="probe.git_commits.invalid_entry",
                reference=ctx.reference,
                raw={"rev": rev, "log": dict(command.raw), "entry": record},
            )

        commit, author_name, committed_at, subject, body = parts
        if not commit or not author_name or not committed_at or not subject:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git log returned a commit entry missing required text fields",
                diagnostic_code="probe.git_commits.invalid_entry",
                reference=ctx.reference,
                raw={"rev": rev, "log": dict(command.raw), "entry": record},
            )

        normalized_body = body.strip()
        text = subject if not normalized_body else f"{subject}\n\n{normalized_body}"
        items.append(
            {
                "commit": commit,
                "subject": subject,
                "body": normalized_body,
                "text": text,
                "author_name": author_name,
                "committed_at": committed_at,
            }
        )

    return ok(
        summary="Git commit texts inspected successfully",
        outputs={
            "count": len(items),
            "rev": rev,
            "items": items,
            "repository_root": repository_root,
        },
        raw=command.raw,
    )
