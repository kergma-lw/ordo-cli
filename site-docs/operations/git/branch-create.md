# git.branch.create

Create a new local Git branch.

Use this when a workflow needs Git state or Git side effects. In practice: create a new local Git branch.

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
  "start_point": "string | null"
}
```

## Outputs

```json
{
  "branch": "string",
  "start_point": "string"
}
```

## Effects

- create a new local branch

## Failure modes

- `invalid_branch`
- `branch_exists`
- `start_point_not_found`
- `create_blocked`

## Requirements

- None

## Invalidated observations

- `git.branches`
- `git.ref.*`

## Example inputs

### `git.branch.create`

```json
{
  "branch": "string",
  "start_point": "string | null"
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
      "create a new local branch"
    ],
    "examples": [
      {
        "inputs": {
          "branch": "string",
          "start_point": "string | null"
        },
        "reference": "git.branch.create"
      }
    ],
    "failure_modes": [
      "invalid_branch",
      "branch_exists",
      "start_point_not_found",
      "create_blocked"
    ],
    "inputs": {
      "branch": "string",
      "start_point": "string | null"
    },
    "invalidates_observations": [
      "git.branches",
      "git.ref.*"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "branch.create",
    "outputs": {
      "branch": "string",
      "start_point": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.branch.create'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "branch.create",
  "reference": "git.branch.create",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
