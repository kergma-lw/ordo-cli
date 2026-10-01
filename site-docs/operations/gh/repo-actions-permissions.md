# GitHub repo actions permissions

the workflow's GitHub repository context already names the normal repository target and the workflow needs to decide whether GitHub Actions are currently enabled before repo.sync or another hosted mutation proceeds.

Probe GitHub Actions permissions for one repository, including whether Actions are enabled and the current hosted Actions policy shape. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- Later logic needs one typed snapshot of repository Actions policy instead of an opaque shell response.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.

## Result and boundary

- Usable result fact: `repository`.
- Usable result fact: `enabled`.
- Usable result fact: `allowed_actions`.
- Usable result fact: `sha_pinning_required`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Changing the repository Actions enabled state; use connector.gh.repo.actions.permissions.set for that effectful update.
- Inspecting local checkout automation state or workflow-run history; this surface is only the repository Actions permissions snapshot.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.gh`: Parent GitHub connector family for repository, issue, pull-request, project, and repository-Actions operations
- [`connector.gh.repo`](repo.md): Sibling repository identity probe for fork and default-branch facts
- [`connector.gh.repo.actions.permissions.set`](repo-actions-permissions-set.md): Sibling action for setting the repository Actions enabled state after reading the current policy
- [`connector.gh.repo.sync`](repo-sync.md): Sibling repository sync action that workflows may guard with the current Actions policy

## Inspect next

- connector.gh.repo.actions.permissions.set
- connector.gh.repo
- connector.gh.repo.sync

## Exact machine contract

Use `ordo-help operation gh.repo.actions.permissions --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_repo_actions_permissions_probe_step

Read one repository's GitHub Actions permissions before toggling or restoring the hosted Actions enabled state.

```yaml
  - name: read-actions-permissions
    uses: gh.repo.actions.permissions
    register: before
```
### gh_repo_actions_permissions_flow

Read repository Actions permissions, disable Actions explicitly, then restore the prior enabled state through separate leaf actions.

```yaml
version: 0
workflow: gh-repo-actions-permissions
connector_contexts:
  gh:
    repository: acme/public-mirror # Literal ASCII OWNER/REPO default, not a URL or authorization allowlist.
blocks:
- steps:
  - name: read-actions-permissions
    uses: gh.repo.actions.permissions
    register: before
  - name: disable-actions
    uses: gh.repo.actions.permissions.set
    with:
      enabled: false
    register: disabled
  - name: restore-actions
    uses: gh.repo.actions.permissions.set
    with:
      enabled: step.before.outputs.enabled
```
