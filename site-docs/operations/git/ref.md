# git.ref

Read metadata for a Git ref.

Use this when a workflow needs Git state or Git side effects. In practice: read metadata for a Git ref.

- Namespace: `git`
- Kind: `probe`
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
  "exists": "boolean",
  "name": "string",
  "oid": "string | null",
  "repository_root": "string",
  "symbolic": "boolean",
  "symbolic_target": "string | null"
}
```

## Effects

- None

## Failure modes

- `probe_failed`

## Requirements

- None

## Example inputs

### `git.ref`

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
    "effects": [],
    "examples": [
      {
        "inputs": {
          "ref": "string"
        },
        "reference": "git.ref"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {
      "ref": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "ref",
    "outputs": {
      "exists": "boolean",
      "name": "string",
      "oid": "string | null",
      "repository_root": "string",
      "symbolic": "boolean",
      "symbolic_target": "string | null"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.ref'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "ref",
  "reference": "git.ref",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
