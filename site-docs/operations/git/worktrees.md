# git.worktrees

List Git worktrees.

Use this when a workflow needs Git state or Git side effects. In practice: list Git worktrees.

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
  "count": "integer",
  "current_path": "string | null",
  "items": [
    {
      "bare": "boolean",
      "branch": "string | null",
      "current": "boolean",
      "detached": "boolean",
      "head": "string",
      "path": "string"
    }
  ],
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

### `git.worktrees`

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
        "reference": "git.worktrees"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {},
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "worktrees",
    "outputs": {
      "count": "integer",
      "current_path": "string | null",
      "items": [
        {
          "bare": "boolean",
          "branch": "string | null",
          "current": "boolean",
          "detached": "boolean",
          "head": "string",
          "path": "string"
        }
      ],
      "repository_root": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.worktrees'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "worktrees",
  "reference": "git.worktrees",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
