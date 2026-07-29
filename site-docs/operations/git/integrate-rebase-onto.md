# git.integrate.rebase_onto

Rebase a Git branch range onto a new base.

Use this when a workflow needs Git state or Git side effects. In practice: rebase a Git branch range onto a new base.

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
  "onto": "string",
  "upstream": "string"
}
```

## Outputs

```json
{
  "branch": "string",
  "head_commit": "string",
  "onto": "string"
}
```

## Effects

- rebase a non-default branch range onto a new base using rebase --onto semantics

## Failure modes

- `onto_not_found`
- `upstream_not_found`
- `branch_not_found`
- `default_branch_protected`
- `rebase_conflict`
- `rebase_blocked`

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

### `git.integrate.rebase_onto`

```json
{
  "branch": "string",
  "onto": "string",
  "upstream": "string"
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
      "rebase a non-default branch range onto a new base using rebase --onto semantics"
    ],
    "examples": [
      {
        "inputs": {
          "branch": "string",
          "onto": "string",
          "upstream": "string"
        },
        "reference": "git.integrate.rebase_onto"
      }
    ],
    "failure_modes": [
      "onto_not_found",
      "upstream_not_found",
      "branch_not_found",
      "default_branch_protected",
      "rebase_conflict",
      "rebase_blocked"
    ],
    "inputs": {
      "branch": "string",
      "onto": "string",
      "upstream": "string"
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
    "name": "integrate.rebase_onto",
    "outputs": {
      "branch": "string",
      "head_commit": "string",
      "onto": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'git.integrate.rebase_onto'",
    "tags": [
      "git",
      "action"
    ]
  },
  "operation_name": "integrate.rebase_onto",
  "reference": "git.integrate.rebase_onto",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
