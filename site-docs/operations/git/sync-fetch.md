# Git sync fetch

A workflow first needs fresh remote-tracking refs, tags, or branch comparisons before deciding whether merging, rebasing, or pushing is safe.

Fetch refs from one Git remote configured in the local repository so later checks and decisions can see updated remote-tracking state without publishing any local branch back outward.

## Use when

- Use this for inbound synchronization from one named remote, not to publish a local branch to collaborators.
- Use a remote already known to the repository, such as origin or team/origin. The action does not fetch from an ad-hoc destination.

## Result and boundary

- On success, local remote-tracking information for the selected remote is refreshed; no local branch is published.
- If the remote cannot be reached or fetching is blocked, later decisions must not treat remote state as refreshed.
- Returns remote and fetched=true after local remote-tracking information is refreshed. Access or transport blocks leave later decisions without refreshed state.

## What to provide

- `remote`: required; provide a configured remote name such as origin or team/origin.

## Do not use for

- Publishing local commits to a remote; use connector.git.sync.push when the workflow needs outbound branch publication rather than remote refresh.
- Comparing branch divergence itself; use connector.git.range after fetch when the workflow actually needs ahead/behind facts rather than the refresh action.
- Ad-hoc URLs, paths, or options instead of a repository remote name.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.sync.push`](sync-push.md): Sibling action for publishing one local branch outward after remote state has been refreshed or confirmed
- [`connector.git.range`](range.md): Compare local and remote revision endpoints after fetch updates remote-tracking refs
- [`connector.git.tags`](tags.md): List fetched tags when the workflow cares about release refs after refresh
- [`connector.git.upstream`](upstream.md): Read current-branch tracking context before deciding which remote should be fetched or pushed

## Exact machine contract

Use `ordo-help operation git.sync.fetch --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_sync_fetch_step

Refresh one explicit configured remote name (origin or team/origin when configured), validated during run before transport, before comparing branch divergence.

```yaml
      - name: fetch-remote-state
        uses: git.sync.fetch
        with:
          remote: inputs.remote_name # Run checks exact configured-name membership before transport.
```
### git_sync_roundtrip_flow

Fetch from one explicit configured remote name, inspect divergence and upstream context, then push one local branch to that same name; explicit naming keeps the roundtrip target clear.

```yaml
version: 0
workflow: refresh-and-publish-git-branch
inputs:
  remote_name: {} # Exact configured name, e.g. origin or team/origin, not an ad-hoc destination.
  branch_name: {}
blocks:
  - guards: []
  - steps:
      - name: fetch-remote-state
        uses: git.sync.fetch
        with:
          remote: inputs.remote_name # Run checks exact configured-name membership before transport.
      - name: inspect-upstream
        uses: git.upstream
        register: upstream_info
      - name: compare-branch-to-upstream
        uses: git.range
        with:
          base: "@{upstream}"
          head: inputs.branch_name
        register: branch_range
      - name: push-branch
        uses: git.sync.push
        with:
          branch: inputs.branch_name
          remote: inputs.remote_name # Keep the configured fetch/push target explicit; omitted/null also resolves nested upstream remote names.
      - name: publish-summary
        publish:
          upstream_ref: step.upstream_info.outputs.upstream_ref
          ahead: step.branch_range.outputs.ahead_count
          summary: "Git sync workflow prepared"
```
