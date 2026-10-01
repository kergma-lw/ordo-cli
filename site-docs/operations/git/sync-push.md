# Git sync push

A workflow is ready to publish one local branch outward after local validation, range checks, or remote refresh have already justified the push decision.

Push one local Git branch to a named remote, or use the current branch's configured upstream remote when none is supplied.

## Use when

- Use this to publish a branch, not merely to refresh remote-tracking refs or inspecting divergence.
- Supply a configured remote name such as origin or team/origin. A remote name is a local Git identifier, not a URL, path, or command option.
- When remote is omitted or null, the requested branch must be the current branch and have a configured upstream remote. The action refuses to guess otherwise.
- The action checks that the branch and selected remote are available before pushing.

## Result and boundary

- On success, the named remote has the current local branch revision for the branch that was pushed.
- A rejected non-fast-forward push leaves the remote branch unchanged. Fetch and reconcile the divergence before trying again.
- Other push blocks, such as unavailable branch or remote access, do not claim that publication occurred.
- Returns remote and branch after publication. A rejected non-fast-forward push leaves the remote branch unchanged; unavailable branch, destination, access, or other blocks do not claim publication.

## What to provide

- `branch`: required; provide the local branch to publish. `remote`: optional; provide a configured remote name or null. Omit it only when this is the current branch and it has a configured upstream destination.

## Do not use for

- Refreshing local knowledge of remote refs; use connector.git.sync.fetch for inbound synchronization before or instead of publishing.
- Guessing whether a push would be fast-forward-safe without wanting to publish yet; use connector.git.range or connector.git.upstream for that read-only decision context first.
- Ad-hoc URLs, paths, or options instead of configured remote names.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.sync.fetch`](sync-fetch.md): Sibling action for refreshing remote-tracking refs before a later push decision or rejection recovery
- [`connector.git.upstream`](upstream.md): Read the current branch's configured upstream remote when remote is omitted
- [`connector.git.range`](range.md): Compare ahead/behind facts when the workflow first needs to know whether the push should succeed as fast-forward
- [`connector.git.branch`](branch.md): Read current branch identity when the workflow first needs to confirm which branch should be published

## Exact machine contract

Use `ordo-help operation git.sync.push --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_sync_push_step

Publish one local branch to an explicit configured remote name after refresh and inspection. Omitted/null remote instead uses the current branch's exact configured upstream remote, including nested names; run validates membership before transport.

```yaml
      - name: push-branch
        uses: git.sync.push
        with:
          branch: inputs.branch_name
          remote: inputs.remote_name # Keep the configured fetch/push target explicit; omitted/null also resolves nested upstream remote names.
```
