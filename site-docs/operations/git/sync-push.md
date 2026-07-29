# git.sync.push

Push a local Git branch to a remote.

Use this when a workflow needs Git state or Git side effects. In practice: push a local Git branch to a remote.

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
  "branch": "string",
  "remote": "string | null"
}
```

## Outputs

```json
{
  "branch": "string",
  "remote": "string"
}
```

## Effects

- push a local branch to a remote

## Failure modes

- `branch_not_found`
- `remote_not_found`
- `upstream_remote_missing`
- `non_fast_forward`
- `push_blocked`

## Requirements

- None

## Preflight observations

```json
[
  {
    "probe": "git.branch",
    "with": {}
  },
  {
    "probe": "git.upstream",
    "with": {}
  },
  {
    "probe": "git.range",
    "with": {
      "base": "@{upstream}",
      "head": "{branch}"
    }
  }
]
```

## Example inputs

### `git.sync.push`

```json
{
  "branch": "string",
  "remote": "string | null"
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
      "push a local branch to a remote"
    ],
    "examples": [
      {
        "inputs": {
          "branch": "string",
          "remote": "string | null"
        },
        "reference": "git.sync.push"
      }
    ],
    "failure_modes": [
      "branch_not_found",
      "remote_not_found",
      "upstream_remote_missing",
      "non_fast_forward",
      "push_blocked"
    ],
    "inputs": {
      "branch": "string",
      "remote": "string | null"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "sync.push",
    "outputs": {
      "branch": "string",
      "remote": "string"
    },
    "preflight_observations": [
      {
        "probe": "git.branch",
        "with": {}
      },
      {
        "probe": "git.upstream",
        "with": {}
      },
      {
        "probe": "git.range",
        "with": {
          "base": "@{upstream}",
          "head": "{branch}"
        }
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.sync.push'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "sync.push",
  "reference": "git.sync.push",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
