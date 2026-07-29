# git.commit.amend

Amend the current Git commit.

Use this when a workflow needs Git state or Git side effects. In practice: amend the current Git commit.

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
  "message": "string | null"
}
```

## Outputs

```json
{
  "branch": "string | null",
  "commit": "string",
  "previous_commit": "string"
}
```

## Effects

- rewrite the current HEAD commit

## Failure modes

- `message_invalid`
- `nothing_to_amend`
- `amend_blocked`

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

### `git.commit.amend`

```json
{
  "message": "string | null"
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
      "rewrite the current HEAD commit"
    ],
    "examples": [
      {
        "inputs": {
          "message": "string | null"
        },
        "reference": "git.commit.amend"
      }
    ],
    "failure_modes": [
      "message_invalid",
      "nothing_to_amend",
      "amend_blocked"
    ],
    "inputs": {
      "message": "string | null"
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
    "name": "commit.amend",
    "outputs": {
      "branch": "string | null",
      "commit": "string",
      "previous_commit": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.commit.amend'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "commit.amend",
  "reference": "git.commit.amend",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
