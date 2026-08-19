# fs.file

Observe one filesystem path as one file snapshot with canonical content and file metadata.

Use this when a workflow needs this exact operation surface. In practice: observe one filesystem path as one file snapshot with canonical content and file metadata.

- Namespace: `fs`
- Kind: `probe`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "path": "string"
}
```

## Outputs

```json
{
  "basename": "string",
  "content": "string",
  "extension": "string",
  "exists": "boolean",
  "filename_without_extension": "string",
  "group": "string",
  "kind": "string",
  "line_count": "integer",
  "modified_at": "string",
  "owner": "string",
  "path": "string",
  "permissions": "string",
  "size": "integer"
}
```

## Effects

- None

## Failure modes

- `path_not_found`
- `not_a_file`
- `content_unavailable`
- `probe_failed`

## Requirements

- None

## Example inputs

### `fs.file`

```json
{
  "path": "/workspace/app.env"
}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [],
    "prerequisites": []
  },
  "document_kind": "operation",
  "namespace": "fs",
  "operation": {
    "deprecated": false,
    "effects": [],
    "examples": [
      {
        "inputs": {
          "path": "/workspace/app.env"
        },
        "reference": "fs.file"
      }
    ],
    "failure_modes": [
      "path_not_found",
      "not_a_file",
      "content_unavailable",
      "probe_failed"
    ],
    "inputs": {
      "path": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "file",
    "outputs": {
      "basename": "string",
      "content": "string",
      "extension": "string",
      "exists": "boolean",
      "filename_without_extension": "string",
      "group": "string",
      "kind": "string",
      "line_count": "integer",
      "modified_at": "string",
      "owner": "string",
      "path": "string",
      "permissions": "string",
      "size": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Observe one filesystem path as one file snapshot with canonical content and file metadata.",
    "tags": [
      "fs",
      "probe"
    ]
  },
  "operation_name": "file",
  "reference": "fs.file",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
