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
