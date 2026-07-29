# git.range

Compare two Git refs and report ahead/behind counts.

Use this when a workflow needs Git state or Git side effects. In practice: compare two Git refs and report ahead/behind counts.

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
  "base": "string",
  "head": "string"
}
```

## Outputs

```json
{
  "ahead_count": "integer",
  "base": "string",
  "base_oid": "string",
  "behind_count": "integer",
  "head": "string",
  "head_oid": "string",
  "merge_base_oid": "string | null",
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

### `git.range`

```json
{
  "base": "string",
  "head": "string"
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
          "base": "string",
          "head": "string"
        },
        "reference": "git.range"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {
      "base": "string",
      "head": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "range",
    "outputs": {
      "ahead_count": "integer",
      "base": "string",
      "base_oid": "string",
      "behind_count": "integer",
      "head": "string",
      "head_oid": "string",
      "merge_base_oid": "string | null",
      "repository_root": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.range'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "range",
  "reference": "git.range",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
