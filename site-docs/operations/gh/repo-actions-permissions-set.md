# GitHub repo actions permissions set

the workflow's GitHub repository context already names the normal repository target and the workflow needs to disable or re-enable hosted GitHub Actions there as an explicit step before later repo-level work.

Set the GitHub Actions enabled state for one repository and report the resulting enabled flag together with whether the repository policy changed. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The authored intent is one narrow repository Actions policy mutation, not a hidden multi-step sync helper.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `enabled`: required.

## Result and boundary

- Usable result fact: `repository`.
- Usable result fact: `enabled`.
- Usable result fact: `changed`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails. Required preflight facts must be established before the change is submitted.

## Do not use for

- Reading the current repository Actions policy without changing it; use connector.gh.repo.actions.permissions for that probe.
- Composing a temporary disable-sync-restore sequence inside one action; keep those steps explicit in the workflow instead of hiding orchestration inside this leaf action.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.repo.actions.permissions`](repo-actions-permissions.md): Sibling probe for the current repository Actions policy before or after mutation
- [`connector.gh.repo.sync`](repo-sync.md): Sibling repository sync action that can appear between explicit disable and restore steps
- [`connector.gh.repo`](repo.md): Sibling repository identity probe for repo-level targeting facts
- [`connector.git.sync.fetch`](../git/sync-fetch.md): Local Git sync action when the real target is a local clone rather than hosted Actions policy

## Inspect next

- connector.gh.repo.actions.permissions
- connector.gh.repo.sync
- connector.gh.repo

## Exact machine contract

Use `ordo-help operation gh.repo.actions.permissions.set --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_repo_actions_permissions_set_step

Set one repository's GitHub Actions enabled flag as an explicit leaf mutation step.

```yaml
  - name: Disable Actions
    uses: gh.repo.actions.permissions.set
    with:
      enabled: false
    register: disabled
```
