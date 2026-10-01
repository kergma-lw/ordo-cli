"""git.upstream probe."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git upstream',
  'goal': 'A workflow needs to know whether the current branch has a tracked branch before comparing divergence or deciding whether publishing makes sense.',
   'summary': 'Observe the current branch tracking relationship, including whether one exists and the related remote and branch names.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to know whether the current branch tracks one upstream before comparing '
                         'ahead/behind state or deciding whether pushing makes sense.',
                           'Later logic needs the tracked branch relationship for the current branch rather than a repository-wide inventory.']},
               {'heading': 'Do not use for',
                'items': ['Reading repository-root or default-branch facts; use connector.git.repo for '
                          'repository-level context.',
                         'Comparing current branch divergence against its upstream; use connector.git.range when the '
                         'workflow needs ahead/behind math after choosing base and head endpoints.',
                           'Determining destinations, access, or publication safety.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.repo',
                                'summary': 'Read repository-level facts before or alongside '
                                          'upstream-tracking inspection'},
                              {'handle': 'connector.git.branch',
                                'summary': 'Read current branch identity when the workflow first needs the '
                                          'branch name itself'},
                              {'handle': 'connector.git.range',
                                'summary': 'Compare ahead/behind and merge-base facts after an upstream '
                                          'target is known'},
                              {'handle': 'connector.git.sync.push',
                                'summary': 'Push once upstream-tracking context '
                                          'has been confirmed'}]},
              ]})

def info():
    return probe(
        name="upstream",
        human=git_human(HUMAN, provide="No inputs are required; use the current checkout whose tracked branch relationship matters.", result="Returns configured, branch, upstream_ref, remote, remote_branch, and repository_root. A detached checkout or branch without tracking is reported with configured=false; unavailable or inconsistent tracking information fails without a guessed result."),
        summary="Inspect the exact configured upstream remote, including nested names, and its conventional local tracking-tail branch",
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

    raw = {"branch": dict(branch_outcome.raw), "upstream": dict(command.raw)}
    try:
        remote_command = ctx.command(
            ["git", "config", "--get", f"branch.{branch}.remote"],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git upstream remote configuration lookup failed",
            diagnostic_code="probe.git_upstream.remote_lookup_failed",
            reference=ctx.reference,
            raw=raw,
        )

    remote = remote_command.stdout
    if isinstance(remote, str):
        remote = remote.removesuffix("\n")
    if not isinstance(remote, str) or not remote or remote == "." or remote.startswith("-") or any(char.isspace() for char in remote):
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git upstream configuration returned an unsupported remote name",
            diagnostic_code="probe.git_upstream.invalid_remote",
            reference=ctx.reference,
            raw=raw,
        )

    try:
        ref_command = ctx.command(
            ["git", "rev-parse", "--symbolic-full-name", "@{upstream}"],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git canonical upstream ref lookup failed",
            diagnostic_code="probe.git_upstream.ref_lookup_failed",
            reference=ctx.reference,
            raw=raw,
        )

    full_ref = ref_command.stdout
    if isinstance(full_ref, str):
        full_ref = full_ref.removesuffix("\n")
    prefix = f"refs/remotes/{remote}/"
    remote_branch = full_ref[len(prefix) :] if isinstance(full_ref, str) and full_ref.startswith(prefix) else ""
    if (
        not remote_branch
        or any(char.isspace() for char in remote_branch)
        or upstream_ref not in (full_ref, f"{remote}/{remote_branch}", f"remotes/{remote}/{remote_branch}")
    ):
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git upstream command returned an unsupported upstream ref format",
            diagnostic_code="probe.git_upstream.invalid_ref",
            reference=ctx.reference,
            raw=raw,
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
        raw=raw,
    )
