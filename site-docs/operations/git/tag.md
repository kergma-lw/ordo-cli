# git.tag

Read tag.

Use this when a workflow needs Git state or Git side effects. In practice: read tag.

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
  "name": "string"
}
```

## Outputs

```json
{
  "annotated": "boolean | null",
  "exists": "boolean",
  "name": "string",
  "oid": "string | null",
  "ref": "string",
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

### `git.tag`

```json
{
  "name": "string"
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
          "name": "string"
        },
        "reference": "git.tag"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {
      "name": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "tag",
    "outputs": {
      "annotated": "boolean | null",
      "exists": "boolean",
      "name": "string",
      "oid": "string | null",
      "ref": "string",
      "repository_root": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.tag'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "tag",
  "reference": "git.tag",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
