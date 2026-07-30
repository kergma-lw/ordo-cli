# git.commit.create

Create a new Git commit from the current index.

Use this when a workflow needs Git state or Git side effects. In practice: create a new Git commit from the current index.

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
  "message": "string"
}
```

## Outputs

```json
{
  "branch": "string | null",
  "commit": "string"
}
```

## Effects

- create a new commit from the current index

## Failure modes

- `message_invalid`
- `nothing_to_commit`
- `commit_blocked`

## Requirements

- None

## Invalidated observations

- `git.ref.*`
- `git.tag`
- `git.tags`
- `git.worktree`
- `git.worktrees`
- `git.state`
- `git.range`
- `git.commits`

## Example inputs

### `git.commit.create`

```json
{
  "message": "string"
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
      "create a new commit from the current index"
    ],
    "examples": [
      {
        "inputs": {
          "message": "string"
        },
        "reference": "git.commit.create"
      }
    ],
    "failure_modes": [
      "message_invalid",
      "nothing_to_commit",
      "commit_blocked"
    ],
    "inputs": {
      "message": "string"
    },
    "invalidates_observations": [
      "git.ref.*",
      "git.tag",
      "git.tags",
      "git.worktree",
      "git.worktrees",
      "git.state",
      "git.range",
      "git.commits"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "commit.create",
    "outputs": {
      "branch": "string | null",
      "commit": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.commit.create'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "commit.create",
  "reference": "git.commit.create",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
