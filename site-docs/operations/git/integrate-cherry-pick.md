# git.integrate.cherry_pick

Cherry-pick a Git commit onto the current checkout.

Use this when a workflow needs Git state or Git side effects. In practice: cherry-pick a Git commit onto the current checkout.

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
  "head_commit": "string",
  "picked_commit": "string"
}
```

## Effects

- apply a target commit onto the current checkout as a new commit

## Failure modes

- `commit_not_found`
- `merge_commit_not_supported`
- `cherry_pick_conflict`
- `cherry_pick_blocked`

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

### `git.integrate.cherry_pick`

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
      "apply a target commit onto the current checkout as a new commit"
    ],
    "examples": [
      {
        "inputs": {
          "commit": "string"
        },
        "reference": "git.integrate.cherry_pick"
      }
    ],
    "failure_modes": [
      "commit_not_found",
      "merge_commit_not_supported",
      "cherry_pick_conflict",
      "cherry_pick_blocked"
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
    "name": "integrate.cherry_pick",
    "outputs": {
      "branch": "string | null",
      "head_commit": "string",
      "picked_commit": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.integrate.cherry_pick'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "integrate.cherry_pick",
  "reference": "git.integrate.cherry_pick",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
