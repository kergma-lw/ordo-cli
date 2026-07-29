# git.index.add_all

Stage all current worktree changes.

Use this when a workflow needs Git state or Git side effects. In practice: stage all current worktree changes.

- Namespace: `git`
- Kind: `action`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{}
```

## Outputs

```json
{
  "staged": "boolean"
}
```

## Effects

- stage all current worktree changes into the index

## Failure modes

- `stage_blocked`

## Requirements

- None

## Invalidated observations

- `git.worktree`
- `git.state`

## Example inputs

### `git.index.add_all`

```json
{}
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
      "stage all current worktree changes into the index"
    ],
    "examples": [
      {
        "inputs": {},
        "reference": "git.index.add_all"
      }
    ],
    "failure_modes": [
      "stage_blocked"
    ],
    "inputs": {},
    "invalidates_observations": [
      "git.worktree",
      "git.state"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "index.add_all",
    "outputs": {
      "staged": "boolean"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.index.add_all'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "index.add_all",
  "reference": "git.index.add_all",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
