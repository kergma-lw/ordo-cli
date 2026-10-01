"""git.branches probe."""

from __future__ import annotations

from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git branches',
 'goal': 'A workflow needs one branch inventory scan before choosing, creating, deleting, or publishing branch-related '
         'state.',
  'summary': 'List local and remote Git branches together with '
            'the current branch marker.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs one branch inventory scan before choosing, creating, deleting, or '
                         'publishing branch-related state.',
                         'Later logic needs to compare the current branch against the available local or remote branch '
                         'set, not just read one current branch name.']},
              {'heading': 'Do not use for',
               'items': ['Reading only the current checkout context; use connector.git.branch for the cheaper '
                          'current-branch lookup.',
                         'Mutating branch state; use connector.git.branch.create, connector.git.branch.delete, or '
                         'connector.git.branch.switch for those actions.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.branch',
                                'summary': 'Read only the current checkout branch instead of the full '
                                          'inventory'},
                              {'handle': 'connector.git.branch.create',
                               'summary': 'Sibling action for adding one new local branch after inventory review'},
                              {'handle': 'connector.git.branch.delete',
                               'summary': 'Sibling action for removing one local branch after inventory review'},
                              {'handle': 'connector.git.ref',
                                'summary': 'Check one explicit ref when a full inventory is broader '
                                          'than needed'}]},
              {'heading': 'Examples', 'items': ['git.branches with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.branch', 'connector.git.branch.create', 'connector.git.branch.delete']}]})

def info():
    return probe(
        name="branches",
        human=git_human(HUMAN, provide="No inputs are required; run from the repository whose branch choices the workflow needs.", result="Returns count, current, items with name, ref, kind, and current marker, plus repository_root. The inventory is a point-in-time observation and has no partial result when it is unreadable."),
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
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git bootstrap did not provide a usable repository root",
            diagnostic_code="probe.git_branches.repo_root_missing",
            reference=ctx.reference,
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
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git branch inventory returned an unexpected line format",
                diagnostic_code="probe.git_branches.invalid_line",
                reference=ctx.reference,
                raw={"branches": dict(command.raw), "line": line},
            )
        head_marker, ref, short_name = parts
        if head_marker not in {"*", " "}:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git branch inventory returned an unsupported current-branch marker",
                diagnostic_code="probe.git_branches.invalid_line",
                reference=ctx.reference,
                raw={"branches": dict(command.raw), "line": line},
            )
        if not ref or not short_name:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git branch inventory returned an entry without a ref or short name",
                diagnostic_code="probe.git_branches.invalid_line",
                reference=ctx.reference,
                raw={"branches": dict(command.raw), "line": line},
            )

        kind = _classify_ref(ref)
        if kind is None:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git branch inventory returned an unsupported ref kind",
                diagnostic_code="probe.git_branches.invalid_ref_kind",
                reference=ctx.reference,
                raw={"branches": dict(command.raw), "line": line, "ref": ref},
            )

        current = head_marker == "*"
        if current:
            if current_name is not None:
                return fail_with_diagnostic(
                    code="probe_failed",
                    summary="Git branch inventory reported more than one current branch",
                    diagnostic_code="probe.git_branches.multiple_current",
                    reference=ctx.reference,
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
