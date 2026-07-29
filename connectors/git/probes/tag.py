"""git.tag probe."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe


def info():
    return probe(
        name="tag",
        inputs={"name": "string"},
        outputs={
            "name": "string",
            "ref": "string",
            "exists": "boolean",
            "oid": "string | null",
            "annotated": "boolean | null",
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
            diagnostic_code="probe.git_tag.repo_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    tag_name = ctx.input("name")
    if not isinstance(tag_name, str) or not tag_name.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.tag requires a non-empty name input",
            diagnostic_code="probe.git_tag.invalid_input",
            reference=ctx.reference,
            raw={"name": tag_name},
        )

    ref = f"refs/tags/{tag_name}"
    raw: dict[str, object] = {}

    try:
        oid_command = ctx.command(
            ["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{object}}"],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 128:
            raw["oid"] = dict(exc.outcome.raw)
            return ok(
                summary="Git tag inspected successfully",
                outputs={
                    "name": tag_name,
                    "ref": ref,
                    "exists": False,
                    "oid": None,
                    "annotated": None,
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
            summary="Git rev-parse returned an empty oid for an existing tag",
            diagnostic_code="probe.git_tag.empty_oid",
            reference=ctx.reference,
            raw=raw,
        )

    type_command = ctx.command(
        ["git", "cat-file", "-t", ref],
        failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
    )
    raw["type"] = dict(type_command.raw)
    object_type = type_command.stdout.strip()
    if object_type not in {"tag", "commit"}:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git cat-file returned an unsupported tag object type",
            diagnostic_code="probe.git_tag.invalid_object_type",
            reference=ctx.reference,
            raw={**raw, "type": object_type},
        )

    return ok(
        summary="Git tag inspected successfully",
        outputs={
            "name": tag_name,
            "ref": ref,
            "exists": True,
            "oid": oid,
            "annotated": object_type == "tag",
            "repository_root": repository_root,
        },
        raw=raw,
    )
