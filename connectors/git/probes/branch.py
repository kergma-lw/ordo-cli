"""git.branch probe."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git branch',
  'goal': 'A workflow needs current checkout context before deciding whether branch-specific actions or branch '
         'guards are appropriate.',
  'summary': 'Read the currently checked out local Git branch and report whether the repository is on a named branch '
            'or in detached HEAD state.',
 'sections': [{'heading': 'Use when',
                'items': ['A workflow needs current checkout context before deciding whether branch-specific '
                         'actions or branch guards are appropriate.',
                         'Later logic only needs the current branch name, ref, or detached flag rather than a full '
                         'branch inventory.']},
              {'heading': 'Do not use for',
               'items': ['Listing many local and remote branches; use connector.git.branches for the inventory '
                          'operation.',
                         'Creating, deleting, or switching branches; use the narrower connector.git.branch.create, '
                         'connector.git.branch.delete, or connector.git.branch.switch actions for mutation.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.branches',
                                'summary': 'List all branches instead of only the current '
                                          'checkout context'},
                              {'handle': 'connector.git.branch.switch',
                                'summary': 'Change the current checkout after confirming '
                                          'the current branch context'},
                              {'handle': 'connector.git.repo',
                                'summary': 'Read repository-level facts such as root path and default '
                                          'branch'},
                              {'handle': 'connector.git.state',
                                'summary': 'Read broader worktree state when branch name alone is not '
                                          'enough'}]},
              {'heading': 'Examples', 'items': ['git.branch with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.branches', 'connector.git.branch.switch', 'connector.git.state']}]})

def info():
    return probe(
        name="branch",
        human=git_human(HUMAN, provide="No inputs are required; run from the checkout whose current branch later steps depend on.", result="Returns value, ref, detached, and repository_root. In detached state value and ref are null rather than a branch name; unreadable repository state has no successful result."),
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
