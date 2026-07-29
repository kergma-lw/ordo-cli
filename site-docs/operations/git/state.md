# git.state

Read the current Git working-state summary.

Use this when a workflow needs Git state or Git side effects. In practice: read the current Git working-state summary.

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
  "branch": "string | null",
  "detached": "boolean",
  "has_staged_changes": "boolean",
  "has_unstaged_changes": "boolean",
  "has_untracked": "boolean",
  "repository_root": "string",
  "stash_count": "integer",
  "worktree_clean": "boolean"
}
```

## Effects

- None

## Failure modes

- `probe_failed`

## Requirements

- None

## Example inputs

### `git.state`

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
        "reference": "git.state"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {},
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "state",
    "outputs": {
      "branch": "string | null",
      "detached": "boolean",
      "has_staged_changes": "boolean",
      "has_unstaged_changes": "boolean",
      "has_untracked": "boolean",
      "repository_root": "string",
      "stash_count": "integer",
      "worktree_clean": "boolean"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.state'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "state",
  "reference": "git.state",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
