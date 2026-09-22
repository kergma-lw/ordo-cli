# git.branch.delete

Delete a local Git branch.

Use this when a workflow needs Git state or Git side effects. In practice: delete a local Git branch.

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
  "force": "boolean"
}
```

## Outputs

```json
{
  "branch": "string"
}
```

## Effects

- delete a local non-default branch

## Failure modes

- `input_error`
- `branch_not_found`
- `branch_checked_out`
- `default_branch_protected`
- `branch_not_merged`
- `delete_blocked`

## Requirements

- None

## Invalidated observations

- `git.branches`
- `git.ref.*`

## Example inputs

### `git.branch.delete`

```json
{
  "branch": "string",
  "force": "boolean"
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
      "delete a local non-default branch"
    ],
    "examples": [
      {
        "inputs": {
          "branch": "string",
          "force": "boolean"
        },
        "reference": "git.branch.delete"
      }
    ],
    "failure_modes": [
      "input_error",
      "branch_not_found",
      "branch_checked_out",
      "default_branch_protected",
      "branch_not_merged",
      "delete_blocked"
    ],
    "inputs": {
      "branch": "string",
      "force": "boolean"
    },
    "invalidates_observations": [
      "git.branches",
      "git.ref.*"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "branch.delete",
    "outputs": {
      "branch": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Delete a local non-default branch; optional boolean force defaults to false (-d), true uses -D.",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "branch.delete",
  "reference": "git.branch.delete",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
