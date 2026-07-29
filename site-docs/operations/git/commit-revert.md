# git.commit.revert

Create a Git commit that reverts another commit.

Use this when a workflow needs Git state or Git side effects. In practice: create a Git commit that reverts another commit.

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
  "commit": "string"
}
```

## Outputs

```json
{
  "branch": "string | null",
  "revert_commit": "string",
  "reverted_commit": "string"
}
```

## Effects

- create a new commit that reverts a target commit

## Failure modes

- `commit_not_found`
- `merge_commit_not_supported`
- `revert_conflict`
- `revert_blocked`

## Requirements

- None

## Invalidated observations

- `git.ref.*`
- `git.worktree`
- `git.worktrees`
- `git.state`
- `git.range`
- `git.commits`

## Example inputs

### `git.commit.revert`

```json
{
  "commit": "string"
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
      "create a new commit that reverts a target commit"
    ],
    "examples": [
      {
        "inputs": {
          "commit": "string"
        },
        "reference": "git.commit.revert"
      }
    ],
    "failure_modes": [
      "commit_not_found",
      "merge_commit_not_supported",
      "revert_conflict",
      "revert_blocked"
    ],
    "inputs": {
      "commit": "string"
    },
    "invalidates_observations": [
      "git.ref.*",
      "git.worktree",
      "git.worktrees",
      "git.state",
      "git.range",
      "git.commits"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "commit.revert",
    "outputs": {
      "branch": "string | null",
      "revert_commit": "string",
      "reverted_commit": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.commit.revert'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "commit.revert",
  "reference": "git.commit.revert",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
