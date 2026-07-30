# git.integrate.merge

Merge a Git ref into the current checkout.

Use this when a workflow needs Git state or Git side effects. In practice: merge a Git ref into the current checkout.

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
  "ref": "string"
}
```

## Outputs

```json
{
  "branch": "string | null",
  "head_commit": "string",
  "merged_ref": "string"
}
```

## Effects

- integrate a target ref into the current checkout using merge semantics

## Failure modes

- `ref_not_found`
- `merge_conflict`
- `merge_blocked`

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

### `git.integrate.merge`

```json
{
  "ref": "string"
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
      "integrate a target ref into the current checkout using merge semantics"
    ],
    "examples": [
      {
        "inputs": {
          "ref": "string"
        },
        "reference": "git.integrate.merge"
      }
    ],
    "failure_modes": [
      "ref_not_found",
      "merge_conflict",
      "merge_blocked"
    ],
    "inputs": {
      "ref": "string"
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
    "name": "integrate.merge",
    "outputs": {
      "branch": "string | null",
      "head_commit": "string",
      "merged_ref": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.integrate.merge'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "integrate.merge",
  "reference": "git.integrate.merge",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
