"""git.sync.push action."""

from __future__ import annotations

from connectors.git.actions._shared import map_nonzero, require_local_branch
from connectors.git.actions.sync._shared import require_configured_remote
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok, preflight_observation
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git sync push',
  'goal': 'A workflow is ready to publish one local branch outward after local validation, range checks, or remote '
          'refresh have already justified the push decision.',
  'summary': 'Push one local Git branch to a named remote, or use the current branch\'s configured upstream remote when none is supplied.',
  'sections': [{'heading': 'Use when',
                'items': ['A workflow is ready to publish one local branch outward after local validation, range '
                          'checks, or remote refresh have already justified the push decision.',
                          'Use this to publish a branch, not merely to refresh '
                          'remote-tracking refs or inspecting divergence.',
                          'Supply a configured remote name such as origin or team/origin. A remote name is a local Git '
                          'identifier, not a URL, path, or command option.',
                            'When remote is omitted or null, the requested branch must be the current branch and have a '
                            'configured upstream remote. The action refuses to guess otherwise.',
                           'The action checks that the branch and selected remote are available before pushing.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the named remote has the current local branch revision for the branch that was '
                         'pushed.',
                         'A rejected non-fast-forward push leaves the remote branch unchanged. Fetch and reconcile the '
                         'divergence before trying again.',
                         'Other push blocks, such as unavailable branch or remote access, do not claim that publication '
                         'occurred.']},
              {'heading': 'What to provide',
               'items': ['Provide the local branch to publish and, when it is not using its usual destination, the '
                         'repository remote to receive it.']},
              {'heading': 'Do not use for',
               'items': ['Refreshing local knowledge of remote refs; use connector.git.sync.fetch for inbound '
                         'synchronization before or instead of publishing.',
                         'Guessing whether a push would be fast-forward-safe without wanting to publish yet; use '
                         'connector.git.range or connector.git.upstream for that read-only decision context first.',
                          'Ad-hoc URLs, paths, or options instead of configured remote names.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.sync.fetch',
                               'summary': 'Sibling action for refreshing remote-tracking refs before a later push '
                                          'decision or rejection recovery'},
                              {'handle': 'connector.git.upstream',
                                'summary': "Read the current branch's configured upstream remote "
                                          'when remote is omitted'},
                              {'handle': 'connector.git.range',
                                'summary': 'Compare ahead/behind facts when the workflow first needs to know '
                                          'whether the push should succeed as fast-forward'},
                              {'handle': 'connector.git.branch',
                                'summary': 'Read current branch identity when the workflow first needs to '
                                          'confirm which branch should be published'}]},
              {'heading': 'Examples',
               'items': ['git.sync.push with inputs {"branch": "feature/demo", "remote": "origin"}',
                         'git.sync.push with inputs {"branch": "feature/demo", "remote": "team/origin"}',
                         'git.sync.push with inputs {"branch": "feature/demo", "remote": null}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.sync.fetch', 'connector.git.upstream', 'connector.git.range']}]})

def info():
    return action(
        name="sync.push",
        human=git_human(HUMAN, provide="`branch`: required; provide the local branch to publish. `remote`: optional; provide a configured remote name or null. Omit it only when this is the current branch and it has a configured upstream destination.", result="Returns remote and branch after publication. A rejected non-fast-forward push leaves the remote branch unchanged; unavailable branch, destination, access, or other blocks do not claim publication."),
        summary="Push to a configured remote name; omitted or null remote uses the current branch's upstream-derived name, validated against configured names",
        inputs={"branch": "string", "remote": "string | null"},
        effects=("push a local branch to a remote",),
        outputs={"remote": "string", "branch": "string"},
        failure_modes=("branch_not_found", "remote_not_found", "upstream_remote_missing", "non_fast_forward", "push_blocked"),
        invalidates_observations=(),
        preflight_observations=(
            preflight_observation(probe="git.branch"),
            preflight_observation(probe="git.upstream"),
            preflight_observation(probe="git.range", with_={"base": "@{upstream}", "head": "{branch}"}),
        ),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch = str(ctx.input("branch"))

    missing_branch = require_local_branch(ctx, branch)
    if missing_branch is not None:
        return missing_branch

    remote = _optional_remote(ctx)
    if isinstance(remote, OperationOutcome):
        return remote
    if remote is None:
        remote = _resolve_upstream_remote(ctx, branch)
        if isinstance(remote, OperationOutcome):
            return remote

    remote = require_configured_remote(ctx, remote, "push_blocked")
    if isinstance(remote, OperationOutcome):
        return remote

    try:
        command = ctx.command(["git", "push", remote, branch], failures={"os_error": "push_blocked", "nonzero": "push_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(
                ("does not appear to be a git repository", "remote_not_found", f"Remote '{remote}' was not found", "action.git.remote_not_found"),
                ("non-fast-forward", "non_fast_forward", f"Push of branch '{branch}' to remote '{remote}' was rejected as non-fast-forward", "action.git.push_non_fast_forward"),
                ("fetch first", "non_fast_forward", f"Push of branch '{branch}' to remote '{remote}' requires fetching first", "action.git.push_non_fast_forward"),
            ),
            fallback_summary=f"Pushing branch '{branch}' to remote '{remote}' failed",
        )

    return ok(
        summary=f"Pushed branch '{branch}' to remote '{remote}'",
        outputs={"remote": remote, "branch": branch},
        raw=command.raw,
    )


def _optional_remote(ctx: OperationContext) -> object | OperationOutcome:
    try:
        value = ctx.input("remote")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome
    return value


def _resolve_upstream_remote(ctx: OperationContext, branch: str) -> str | OperationOutcome:
    upstream = ctx.call("upstream")
    if upstream.status != "ok":
        return upstream

    configured = upstream.outputs.get("configured")
    upstream_branch = upstream.outputs.get("branch")
    remote = upstream.outputs.get("remote")
    if configured is True and upstream_branch == branch and isinstance(remote, str) and remote.strip():
        return remote

    return fail_with_diagnostic(
        code="upstream_remote_missing",
        summary=f"Branch '{branch}' does not have a configured upstream remote",
        diagnostic_code="action.git.upstream_remote_missing",
        reference=ctx.reference,
        raw={"upstream": dict(upstream.raw)},
    )
