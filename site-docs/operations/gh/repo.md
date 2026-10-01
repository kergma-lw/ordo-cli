# GitHub repo

the workflow's GitHub repository context already names the normal repository target and the workflow needs one repository-level fact probe before deciding whether repo.sync can apply cleanly.

Probe one GitHub repository as a normalized identity and fork snapshot, including its default branch, fork status, parent repository, and archived flag. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.

## Use when

- Later logic needs the repository's canonical name, default branch, or parent fork relationship rather than issue-, PR-, or project-level facts.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.

## Result and boundary

- Usable result fact: `id`.
- Usable result fact: `repository`.
- Usable result fact: `default_branch`.
- Usable result fact: `is_fork`.
- Usable result fact: `parent_repository`.
- Usable result fact: `archived`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Syncing the repository's default branch; use connector.gh.repo.sync for that effectful fork-sync operation.
- Inspecting pull requests, issues, or GitHub Project membership; those remain separate narrower GitHub surfaces.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.gh`: Parent GitHub connector family for repository, issue, pull-request, and project operations
- [`connector.gh.repo.sync`](repo-sync.md): Sibling action for syncing one fork repository default branch after this probe confirms fork facts
- [`connector.git.repo`](../git/repo.md): Sibling local Git repository probe for checkout-root and worktree facts rather than remote GitHub repository identity
- [`connector.gh.pr`](pr.md): Sibling GitHub probe for pull-request facts once the workflow moves from repository-level to PR-level logic

## Inspect next

- connector.gh.repo.sync
- connector.git.repo
- connector.gh.pr

## Exact machine contract

Use `ordo-help operation gh.repo --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_repo_probe_step

Inspect one GitHub repository's normalized identity and fork relationship before deciding whether hosted fork sync applies.

```yaml
  - name: inspect-repository
    uses: gh.repo
    register: repo_snapshot
```
### gh_repo_sync_flow

Inspect one hosted fork repository, sync its default branch from the parent repository, then publish the synced branch summary.

```yaml
version: 0
workflow: gh-repo-sync
connector_contexts:
  gh:
    repository: acme/public-mirror # Literal ASCII OWNER/REPO default, not a URL or authorization allowlist.
blocks:
- steps:
  - name: inspect-repository
    uses: gh.repo
    register: repo_snapshot
  - name: sync-default-branch
    uses: gh.repo.sync
    register: sync_result
  - name: publish-summary
    value:
      repository: step.repo_snapshot.outputs.repository
      branch: step.sync_result.outputs.branch
      upstream_repository: step.sync_result.outputs.upstream_repository
```
