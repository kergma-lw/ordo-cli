# git.sync.fetch

Fetch Git refs from a remote.

Use this when a workflow needs Git state or Git side effects. In practice: fetch Git refs from a remote.

- Namespace: `git`
- Kind: `action`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "remote": "string"
}
```

## Outputs

```json
{
  "fetched": "boolean",
  "remote": "string"
}
```

## Effects

- fetch refs from a remote into the local repository

## Failure modes

- `remote_not_found`
- `fetch_blocked`

## Requirements

- None

## Invalidated observations

- `git.ref.*`
- `git.tag`
- `git.tags`
- `git.branches`
- `git.repo`
- `git.range`
- `git.commits`

## Example inputs

### `git.sync.fetch`

```json
{
  "remote": "string"
}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [
      "repository_root"
    ],
    "prerequisites": [
      "git binary available",
      "inside git repository"
    ]
  },
  "document_kind": "operation",
  "namespace": "git",
  "operation": {
    "deprecated": false,
    "effects": [
      "fetch refs from a remote into the local repository"
    ],
    "examples": [
      {
        "inputs": {
          "remote": "string"
        },
        "reference": "git.sync.fetch"
      }
    ],
    "failure_modes": [
      "remote_not_found",
      "fetch_blocked"
    ],
    "inputs": {
      "remote": "string"
    },
    "invalidates_observations": [
      "git.ref.*",
      "git.tag",
      "git.tags",
      "git.branches",
      "git.repo",
      "git.range",
      "git.commits"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "sync.fetch",
    "outputs": {
      "fetched": "boolean",
      "remote": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.sync.fetch'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "sync.fetch",
  "reference": "git.sync.fetch",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
