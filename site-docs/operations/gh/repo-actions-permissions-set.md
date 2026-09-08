# gh.repo.actions.permissions.set

Set the GitHub Actions enabled state for one repository.

Use this when a workflow needs to inspect or change GitHub state. In practice: set the GitHub Actions enabled state for one repository.

- Namespace: `gh`
- Kind: `action`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "enabled": "boolean",
  "repository": "string"
}
```

## Outputs

```json
{
  "changed": "boolean",
  "enabled": "boolean",
  "repository": "string"
}
```

## Authoring contract

Set the GitHub Actions enabled state for one repository and report the resulting enabled flag together with whether the repository policy changed. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs to disable or re-enable hosted GitHub Actions there as an explicit step before later repo-level work.
- The authored intent is one narrow repository Actions policy mutation, not a hidden multi-step sync helper.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Reading the current repository Actions policy without changing it; use connector.gh.repo.actions.permissions for that probe.
- Composing a temporary disable-sync-restore sequence inside one action; keep those steps explicit in the workflow instead of hiding orchestration inside this leaf action.

### gh_repo_actions_permissions_set_step

Set one repository's GitHub Actions enabled flag as an explicit leaf mutation step.

```yaml
  - name: disable-actions
    uses: gh.repo.actions.permissions.set
    with:
      enabled: false
    register: disabled
```

## Effects

- set the GitHub Actions enabled state for one repository

## Failure modes

- `repository_not_found`
- `set_blocked`

## Requirements

- None

## Preflight observations

```json
[
  {
    "fields": [
      "enabled"
    ],
    "probe": "gh.repo.actions.permissions",
    "with": {}
  }
]
```

## Example inputs

### `gh.repo.actions.permissions.set`

```json
{
  "enabled": false
}
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
    "effects": [
      "set the GitHub Actions enabled state for one repository"
    ],
    "examples": [
      {
        "inputs": {
          "enabled": false
        },
        "reference": "gh.repo.actions.permissions.set"
      }
    ],
    "failure_modes": [
      "repository_not_found",
      "set_blocked"
    ],
    "inputs": {
      "enabled": "boolean",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "repo.actions.permissions.set",
    "outputs": {
      "changed": "boolean",
      "enabled": "boolean",
      "repository": "string"
    },
    "preflight_observations": [
      {
        "fields": [
          "enabled"
        ],
        "probe": "gh.repo.actions.permissions",
        "with": {}
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Set the GitHub Actions enabled state for one repository.",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "repo.actions.permissions.set",
  "reference": "gh.repo.actions.permissions.set",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
