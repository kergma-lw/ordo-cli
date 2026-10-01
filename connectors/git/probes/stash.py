"""git.stash probe."""

from __future__ import annotations

from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git stash',
 'goal': 'A workflow needs to know whether stash entries exist before switching branches, cleaning a worktree, or '
         'deciding whether hidden local work might need recovery.',
  'summary': 'List current Git stash entries, their selectors, and the '
            'repository root they belong to.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to know whether stash entries exist before switching branches, cleaning a '
                         'worktree, or deciding whether hidden local work might need recovery.',
                         'Later logic needs the explicit stash entry list itself rather than only one coarse '
                         'repository-state summary flag.']},
              {'heading': 'Do not use for',
               'items': ['Reading only one combined repository snapshot with branch and worktree flags; use '
                         'connector.git.state when stash count is just one part of a broader readiness summary.',
                         'Inspecting unstaged or staged path details; use connector.git.worktree when the workflow is '
                         'really about dirty files rather than saved stash entries.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.state',
                                'summary': 'Read one broader branch-plus-worktree-plus-stash-count summary '
                                          'instead of the explicit stash entry list'},
                              {'handle': 'connector.git.worktree',
                                'summary': 'Read current dirty-path details when the workflow needs live '
                                          'worktree changes rather than saved stash entries'},
                              {'handle': 'connector.git.branch.switch',
                               'summary': 'Sibling action often guarded by stash awareness when the workflow wants to '
                                          'avoid losing hidden local work during checkout changes'},
                              {'handle': 'connector.git.repo',
                                'summary': 'Read repository-level context when the workflow first needs '
                                          'root and default-branch facts rather than stash inventory'}]},
              {'heading': 'Examples', 'items': ['git.stash with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.state', 'connector.git.worktree', 'connector.git.branch.switch']}]})

def info():
    return probe(
        name="stash",
        human=git_human(HUMAN, provide="No inputs are required; use the repository whose saved local work the workflow must assess.", result="Returns count, ordered items with selector and summary, and repository_root. An unavailable repository or unreadable stash inventory produces no partial result; entries can change after this observation."),
        outputs={
            "count": "integer",
            "items": [
                {
                    "name": "string",
                    "selector": "string",
                    "summary": "string",
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
            diagnostic_code="probe.git_stash.repo_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    command = ctx.command(
        ["git", "stash", "list"],
        failures={
            "os_error": "probe_failed",
            "nonzero": "probe_failed",
        },
    )

    items: list[dict[str, str]] = []
    for line in command.stdout.splitlines():
        if not line:
            continue
        selector, separator, summary = line.partition(": ")
        if not separator:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git stash list returned a line with an unsupported format",
                diagnostic_code="probe.git_stash.invalid_line",
                reference=ctx.reference,
                raw={"stash": dict(command.raw), "line": line},
            )
        if not selector.startswith("stash@{") or not selector.endswith("}"):
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git stash list returned an invalid stash selector",
                diagnostic_code="probe.git_stash.invalid_selector",
                reference=ctx.reference,
                raw={"stash": dict(command.raw), "line": line},
            )
        if not summary:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git stash list returned an entry without a summary",
                diagnostic_code="probe.git_stash.empty_summary",
                reference=ctx.reference,
                raw={"stash": dict(command.raw), "line": line},
            )
        items.append({"name": selector, "selector": selector, "summary": summary})

    return ok(
        summary="Git stash list inspected successfully",
        outputs={
            "count": len(items),
            "items": items,
            "repository_root": repository_root,
        },
        raw=command.raw,
    )
