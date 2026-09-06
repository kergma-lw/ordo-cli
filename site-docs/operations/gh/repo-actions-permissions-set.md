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
