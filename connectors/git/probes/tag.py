"""git.tag probe."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_external_command, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git tag',
 'goal': 'A workflow needs to confirm one specific tag such as v1.2.3 before branching on release presence or '
         'publishing tag metadata.',
  'summary': 'Check one named Git tag and report whether it exists, which ref it occupies, and whether the stored '
            'object is an annotated tag object or a lightweight commit ref.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to confirm one specific tag such as v1.2.3 before branching on release '
                         'presence or publishing tag metadata.',
                         'Later logic needs the single-tag existence result plus the raw tag ref and object identity, '
                         'not a broader tag inventory.']},
              {'heading': 'Do not use for',
                'items': ['Listing or pattern-matching many tags; use connector.git.tags for the inventory.',
                         'Inferring the newest tag by version ordering across many candidates; use connector.git.tags '
                         'and its latest output for that collection-oriented question.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.tags',
                                'summary': 'List tags instead of inspecting one named tag '
                                          'lookup'},
                              {'handle': 'connector.git.ref',
                                'summary': 'Check refs when the workflow cares '
                                          'about refs broadly rather than Git tag semantics specifically'},
                              {'handle': 'connector.git.commits',
                                'summary': 'Read commit history when one tag lookup alone is not '
                                          'enough context'},
                              {'handle': 'connector.git.range',
                                'summary': 'Compare a revision range when the question is broader '
                                          'than one named tag'}]},
              {'heading': 'Examples',
               'items': ['git.tag with inputs {"name": "v1.2.3"}', 'git.tag with inputs {"name": "release-2026-07"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.tags', 'connector.git.ref', 'connector.git.commits']}]})

def info():
    return probe(
        name="tag",
        human=git_human(HUMAN, provide="`name`: required; provide the exact tag to inspect in the current repository.", result="Returns name, ref, exists, oid, annotated, and repository_root. A missing tag succeeds with exists=false and unknown object facts; an invalid name or unreadable repository has no partial result."),
        summary=(
            "Read one Git tag. The `oid` output is the object id resolved for the tag ref itself; "
            "for annotated tags this is the tag object's oid rather than the peeled target commit oid."
        ),
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
        examples=(
            {"reference": "git.tag", "inputs": {"name": "v1.2.3"}},
            {"reference": "git.tag", "inputs": {"name": "release-2026-07"}},
        ),
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
        return fail_external_command(
            code="probe_failed",
            summary="Git tag inspection failed",
            diagnostic_code="probe.git_tag.command_failed",
            reference=ctx.reference,
            details={"name": tag_name},
            raw=exc.outcome.raw,
            tool="git",
        )

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

    try:
        type_command = ctx.command(
            ["git", "cat-file", "-t", ref],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        return fail_external_command(
            code="probe_failed",
            summary="Git tag type inspection failed",
            diagnostic_code="probe.git_tag.command_failed",
            reference=ctx.reference,
            details={"name": tag_name},
            raw=exc.outcome.raw,
            tool="git",
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
