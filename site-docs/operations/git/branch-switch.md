# git.branch.switch

Switch the current checkout to a local Git branch.

Use this when a workflow needs Git state or Git side effects. In practice: switch the current checkout to a local Git branch.

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
  "branch": "string"
}
```

## Outputs

```json
{
  "branch": "string",
  "changed": "boolean"
}
```

## Effects

- switch current checkout to a local branch

## Failure modes

- `branch_not_found`
- `worktree_change_conflict`
- `unresolved_state`
- `switch_blocked`

## Requirements

- None

## Invalidated observations

- `git.branch`
- `git.branches`
- `git.upstream`
- `git.ref.*`
- `git.tag`
- `git.tags`
- `git.worktree`
- `git.worktrees`
- `git.state`
- `git.repo`
- `git.range`
- `git.commits`

## Example inputs

### `git.branch.switch`

```json
{
  "branch": "string"
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
      "switch current checkout to a local branch"
    ],
    "examples": [
      {
        "inputs": {
          "branch": "string"
        },
        "reference": "git.branch.switch"
      }
    ],
    "failure_modes": [
      "branch_not_found",
      "worktree_change_conflict",
      "unresolved_state",
      "switch_blocked"
    ],
    "inputs": {
      "branch": "string"
    },
    "invalidates_observations": [
      "git.branch",
      "git.branches",
      "git.upstream",
      "git.ref.*",
      "git.tag",
      "git.tags",
      "git.worktree",
      "git.worktrees",
      "git.state",
      "git.repo",
      "git.range",
      "git.commits"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "branch.switch",
    "outputs": {
      "branch": "string",
      "changed": "boolean"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.branch.switch'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "branch.switch",
  "reference": "git.branch.switch",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
