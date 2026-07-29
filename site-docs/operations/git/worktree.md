# git.worktree

Read the current Git worktree state.

Use this when a workflow needs Git state or Git side effects. In practice: read the current Git worktree state.

- Namespace: `git`
- Kind: `probe`
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
  "clean": "boolean",
  "dirty_paths": [
    "string"
  ],
  "has_staged_changes": "boolean",
  "has_unstaged_changes": "boolean",
  "has_untracked": "boolean",
  "repository_root": "string"
}
```

## Effects

- None

## Failure modes

- `probe_failed`

## Requirements

- None

## Example inputs

### `git.worktree`

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
    "effects": [],
    "examples": [
      {
        "inputs": {},
        "reference": "git.worktree"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {},
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "worktree",
    "outputs": {
      "clean": "boolean",
      "dirty_paths": [
        "string"
      ],
      "has_staged_changes": "boolean",
      "has_unstaged_changes": "boolean",
      "has_untracked": "boolean",
      "repository_root": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.worktree'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "worktree",
  "reference": "git.worktree",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
