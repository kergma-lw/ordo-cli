"""git.sync.fetch action."""

from __future__ import annotations

from connectors.git.actions._shared import FETCH_INVALIDATION, map_nonzero
from connectors.git.actions.sync._shared import require_configured_remote
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git sync fetch',
 'goal': 'A workflow first needs fresh remote-tracking refs, tags, or branch comparisons before deciding whether '
         'merging, rebasing, or pushing is safe.',
  'summary': 'Fetch refs from one Git remote configured in the local repository so later checks and decisions can see '
            'updated remote-tracking state without publishing any local branch back outward.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow first needs fresh remote-tracking refs, tags, or branch comparisons before '
                          'deciding whether merging, rebasing, or pushing is safe.',
                           'Use this for inbound synchronization from one named remote, not to publish a local '
                          'branch to collaborators.',
                          'Use a remote already known to the repository, such as origin or team/origin. The action does '
                          'not fetch from an ad-hoc destination.']},
              {'heading': 'Result and boundary',
               'items': ['On success, local remote-tracking information for the selected remote is refreshed; no local '
                         'branch is published.',
                         'If the remote cannot be reached or fetching is blocked, later decisions must not treat remote '
                         'state as refreshed.']},
              {'heading': 'Do not use for',
               'items': ['Publishing local commits to a remote; use connector.git.sync.push when the workflow needs '
                         'outbound branch publication rather than remote refresh.',
                         'Comparing branch divergence itself; use connector.git.range after fetch when the workflow '
                         'actually needs ahead/behind facts rather than the refresh action.',
                          'Ad-hoc URLs, paths, or options instead of a repository remote name.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.sync.push',
                               'summary': 'Sibling action for publishing one local branch outward after remote state '
                                          'has been refreshed or confirmed'},
                              {'handle': 'connector.git.range',
                                'summary': 'Compare local and remote revision endpoints after fetch '
                                          'updates remote-tracking refs'},
                              {'handle': 'connector.git.tags',
                                'summary': 'List fetched tags when the workflow cares '
                                          'about release refs after refresh'},
                              {'handle': 'connector.git.upstream',
                                'summary': 'Read current-branch tracking context before deciding which '
                                          'remote should be fetched or pushed'}]},
              {'heading': 'Examples',
               'items': ['git.sync.fetch with inputs {"remote": "origin"}',
                         'git.sync.fetch with inputs {"remote": "team/origin"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.range', 'connector.git.sync.push', 'connector.git.tags']}]})

def info():
    return action(
        name="sync.fetch",
        human=git_human(HUMAN, provide="`remote`: required; provide a configured remote name such as origin or team/origin.", result="Returns remote and fetched=true after local remote-tracking information is refreshed. Access or transport blocks leave later decisions without refreshed state."),
        summary="Fetch from a configured remote name, not a direct URL, path, or option",
        inputs={"remote": "string"},
        effects=("fetch refs from a remote into the local repository",),
        outputs={"remote": "string", "fetched": "boolean"},
        failure_modes=("remote_not_found", "fetch_blocked"),
        invalidates_observations=FETCH_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    remote = require_configured_remote(ctx, ctx.input("remote"), "fetch_blocked")
    if isinstance(remote, OperationOutcome):
        return remote
    try:
        command = ctx.command(["git", "fetch", remote], failures={"os_error": "fetch_blocked", "nonzero": "fetch_blocked"})
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(("does not appear to be a git repository", "remote_not_found", f"Remote '{remote}' was not found", "action.git.remote_not_found"),),
            fallback_summary=f"Fetching from remote '{remote}' failed",
        )

    return ok(
        summary=f"Fetched from remote '{remote}'",
        outputs={"remote": remote, "fetched": True},
        raw=command.raw,
    )
