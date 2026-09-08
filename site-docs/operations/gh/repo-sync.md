# gh.repo.sync

Sync one GitHub fork repository default branch from its parent repository.

Use this when a workflow needs to inspect or change GitHub state. In practice: sync one GitHub fork repository default branch from its parent repository.

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
  "repository": "string"
}
```

## Outputs

```json
{
  "branch": "string",
  "repository": "string",
  "synced": "boolean",
  "upstream_repository": "string"
}
```

## Authoring contract

Sync one GitHub fork repository's default branch from its parent repository and return the synced branch together with the resolved upstream repository name. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.

- connector_contexts.gh.repository already names the normal fork target and the workflow needs to keep its canonical default branch current with the parent repository.
- The authored intent is the GitHub-native fork sync operation itself, not a local git fetch/merge sequence or a repository-settings mutation helper.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Inspecting whether the repository is a fork or what its default branch is; use connector.gh.repo for that read-only fact surface first or separately.
- Local checkout synchronization or worktree mutation; use connector.git.* when the real target is the local repository rather than GitHub-hosted fork state.

### gh_repo_sync_step

Sync one hosted GitHub fork repository's default branch from its parent repository through the published repo.sync action.

```yaml
  - name: sync-default-branch
    uses: gh.repo.sync
    register: sync_result
```

## Effects

- sync one fork repository default branch from its parent repository

## Failure modes

- `repository_not_found`
- `not_a_fork`
- `archived_repository`
- `default_branch_unavailable`
- `sync_blocked`

## Requirements

- None

## Preflight observations

```json
[
  {
    "fields": [
      "is_fork",
      "default_branch",
      "parent_repository",
      "archived"
    ],
    "probe": "gh.repo",
    "with": {}
  }
]
```

## Example inputs

### `gh.repo.sync`

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
    "effects": [
      "sync one fork repository default branch from its parent repository"
    ],
    "examples": [
      {
        "inputs": {},
        "reference": "gh.repo.sync"
      }
    ],
    "failure_modes": [
      "repository_not_found",
      "not_a_fork",
      "archived_repository",
      "default_branch_unavailable",
      "sync_blocked"
    ],
    "inputs": {
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "repo.sync",
    "outputs": {
      "branch": "string",
      "repository": "string",
      "synced": "boolean",
      "upstream_repository": "string"
    },
    "preflight_observations": [
      {
        "fields": [
          "is_fork",
          "default_branch",
          "parent_repository",
          "archived"
        ],
        "probe": "gh.repo",
        "with": {}
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Sync one GitHub fork repository default branch from its parent repository.",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "repo.sync",
  "reference": "gh.repo.sync",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
