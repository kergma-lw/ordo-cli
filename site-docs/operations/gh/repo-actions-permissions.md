# gh.repo.actions.permissions

Read GitHub Actions permissions for one repository.

Use this when a workflow needs to inspect or change GitHub state. In practice: read GitHub Actions permissions for one repository.

- Namespace: `gh`
- Kind: `probe`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "repository": "string"
}
```

## Outputs

```json
{
  "allowed_actions": "string | null",
  "enabled": "boolean",
  "repository": "string",
  "sha_pinning_required": "boolean | null"
}
```

## Authoring contract

Probe GitHub Actions permissions for one repository, including whether Actions are enabled and the current hosted Actions policy shape. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs to decide whether GitHub Actions are currently enabled before repo.sync or another hosted mutation proceeds.
- Later logic needs one typed snapshot of repository Actions policy instead of an opaque gh api response.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Changing the repository Actions enabled state; use connector.gh.repo.actions.permissions.set for that effectful update.
- Inspecting local checkout automation state or workflow-run history; this surface is only the repository Actions permissions snapshot.

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

## Effects

- None

## Failure modes

- `repository_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.repo.actions.permissions`

```json
{}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [
      "host",
      "viewer",
      "scopes",
      "repository"
    ],
    "prerequisites": [
      "gh binary available",
      "GitHub auth available"
    ]
  },
  "document_kind": "operation",
  "namespace": "gh",
  "operation": {
    "deprecated": false,
    "effects": [],
    "examples": [
      {
        "inputs": {},
        "reference": "gh.repo.actions.permissions"
      }
    ],
    "failure_modes": [
      "repository_not_found",
      "probe_failed"
    ],
    "inputs": {
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "repo.actions.permissions",
    "outputs": {
      "allowed_actions": "string | null",
      "enabled": "boolean",
      "repository": "string",
      "sha_pinning_required": "boolean | null"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read GitHub Actions permissions for one repository.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "repo.actions.permissions",
  "reference": "gh.repo.actions.permissions",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
