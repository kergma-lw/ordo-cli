"""Fetch only tag refs from one configured Git remote."""

from __future__ import annotations

from connectors.git.actions._shared import map_nonzero
from connectors.git.actions.sync._shared import require_configured_remote
from connectors.git.human import git_human
from ordo.model.human import declare_human
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, ok


HUMAN = declare_human({"title": "Git sync fetch tags", "goal": "Refresh local tag refs from one configured remote without updating branches or merging work.", "summary": "Fetch only remote tag refs from a configured remote.", "sections": [
    {"heading": "Use when", "items": ["A later decision needs remote tags, but remote-tracking branches must remain unchanged.", "Use a configured remote name, not an ad-hoc URL or path."]},
    {"heading": "Result and boundary", "items": ["`remote` identifies the source and `fetched=true` confirms tag-only fetch completed. The result does not claim that a new tag existed.", "The action neither updates branches nor merges work. It does not force-move conflicting local tags or prune locally retained tags."]},
    {"heading": "Do not use for", "items": ["Refreshing remote-tracking branches; use connector.git.sync.fetch.", "Deleting local tags absent from the remote, forcing a changed tag, or publishing tags."]},
    {"heading": "Related references", "body": "Use these related references when the workflow needs tag facts or broader remote refresh.", "references": [{"handle": "connector.git.tags", "summary": "List local tags after a tag-only fetch."}, {"handle": "connector.git.sync.fetch", "summary": "Refresh the ordinary remote-tracking refs."}]},
]})


def info():
    return action(name="sync.fetch-tags", human=git_human(HUMAN, provide="`remote`: required; provide a configured remote name such as origin.", result="Returns `remote` and `fetched=true` after Git completes a tag-only fetch. A missing remote or tag conflict leaves tag state without confirmed refresh."), summary="Fetch only tag refs from a configured remote, without branch updates", inputs={"remote": "string"}, effects=("fetch only remote tag refs into the local repository",), outputs={"remote": "string", "fetched": "boolean"}, failure_modes=("remote_not_found", "fetch_tags_blocked"), invalidates_observations=("git.tag", "git.tags"), handler=run)


def run(ctx: OperationContext) -> OperationOutcome:
    remote = require_configured_remote(ctx, ctx.input("remote"), "fetch_tags_blocked")
    if isinstance(remote, OperationOutcome):
        return remote
    try:
        command = ctx.command(["git", "fetch", remote, "refs/tags/*:refs/tags/*"], failures={"os_error": "fetch_tags_blocked", "nonzero": "fetch_tags_blocked"})
    except MappedOutcomeError as exc:
        mapped = map_nonzero(ctx, exc, cases=(("does not appear to be a git repository", "remote_not_found", f"Remote '{remote}' was not found", "action.git.remote_not_found"),), fallback_summary=f"Fetching tags from remote '{remote}' failed")
        return exc.outcome if mapped.status == "action_failed" else mapped
    return ok(summary=f"Fetched tags from remote '{remote}'", outputs={"remote": remote, "fetched": True}, raw=command.raw)
