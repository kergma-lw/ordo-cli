# GitHub repo sync

the workflow's GitHub repository context already names the normal fork target and the workflow needs to keep its canonical default branch current with the parent repository.

Sync one GitHub fork repository's default branch from its parent repository and return the synced branch together with the resolved upstream repository name. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.

## Use when

- The authored intent is the GitHub-native fork sync operation itself, not a local git fetch/merge sequence or a repository-settings mutation helper.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.

## Result and boundary

- Usable result fact: `repository`.
- Usable result fact: `branch`.
- Usable result fact: `upstream_repository`.
- Usable result fact: `synced`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails. Required preflight facts must be established before the change is submitted.

## Do not use for

- Inspecting whether the repository is a fork or what its default branch is; use connector.gh.repo for that read-only fact surface first or separately.
- Local checkout synchronization or worktree mutation; use connector.git.* when the real target is the local repository rather than GitHub-hosted fork state.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.repo`](repo.md): Parent repository probe for fork identity and default-branch facts before or after sync
- [`connector.git.sync.fetch`](../git/sync-fetch.md): Sibling local Git action for fetching refs into a local clone rather than syncing a hosted GitHub fork
- [`connector.git.repo`](../git/repo.md): Sibling local Git probe when later workflow logic needs local repository state after remote fork sync
- [`connector.gh.pr`](pr.md): Sibling GitHub probe for PR-level follow-up work once repository sync is complete

## Inspect next

- connector.gh.repo
- connector.git.sync.fetch
- connector.git.repo

## Exact machine contract

Use `ordo-help operation gh.repo.sync --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_repo_sync_step

Sync one hosted GitHub fork repository's default branch from its parent repository through the published repo.sync action.

```yaml
  - name: Sync default branch
    uses: gh.repo.sync
    register: sync_result
```
