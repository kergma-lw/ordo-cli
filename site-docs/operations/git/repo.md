# git.repo

Read Git repository metadata.

Use this when a workflow needs Git state or Git side effects. In practice: read Git repository metadata.

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
  "bare": "boolean",
  "common_dir": "string",
  "default_branch": "string | null",
  "exists": "boolean",
  "git_dir": "string",
  "head_ref": "string | null",
  "inside_work_tree": "boolean",
  "root": "string",
  "worktree_path": "string | null"
}
```

## Effects

- None

## Failure modes

- `probe_failed`

## Requirements

- None

## Example inputs

### `git.repo`

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
        "reference": "git.repo"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {},
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "repo",
    "outputs": {
      "bare": "boolean",
      "common_dir": "string",
      "default_branch": "string | null",
      "exists": "boolean",
      "git_dir": "string",
      "head_ref": "string | null",
      "inside_work_tree": "boolean",
      "root": "string",
      "worktree_path": "string | null"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.repo'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "repo",
  "reference": "git.repo",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
