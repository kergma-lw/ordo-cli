# git.integrate.merge_ff_only

Fast-forward merge a Git ref into the current checkout.

Use this when a workflow needs Git state or Git side effects. In practice: fast-forward merge a Git ref into the current checkout.

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

- integrate a target ref into the current checkout using fast-forward-only semantics

## Failure modes

- `ref_not_found`
- `non_fast_forward`
- `merge_blocked`

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

### `git.integrate.merge_ff_only`

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
      "integrate a target ref into the current checkout using fast-forward-only semantics"
    ],
    "examples": [
      {
        "inputs": {
          "ref": "string"
        },
        "reference": "git.integrate.merge_ff_only"
      }
    ],
    "failure_modes": [
      "ref_not_found",
      "non_fast_forward",
      "merge_blocked"
    ],
    "inputs": {
      "ref": "string"
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
    "name": "integrate.merge_ff_only",
    "outputs": {
      "branch": "string | null",
      "head_commit": "string",
      "merged_ref": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.integrate.merge_ff_only'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "integrate.merge_ff_only",
  "reference": "git.integrate.merge_ff_only",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
