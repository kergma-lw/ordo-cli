# git.tags

Inspect tags.

Use this when a workflow needs Git state or Git side effects. In practice: inspect tags.

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
  "match": "string | null"
}
```

## Outputs

```json
{
  "count": "integer",
  "items": [
    {
      "annotated": "boolean",
      "name": "string",
      "oid": "string",
      "ref": "string"
    }
  ],
  "latest": {
    "annotated": "boolean",
    "name": "string",
    "oid": "string",
    "ref": "string"
  },
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

### `git.tags`

```json
{
  "match": "string | null"
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
          "match": "string | null"
        },
        "reference": "git.tags"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {
      "match": "string | null"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "tags",
    "outputs": {
      "count": "integer",
      "items": [
        {
          "annotated": "boolean",
          "name": "string",
          "oid": "string",
          "ref": "string"
        }
      ],
      "latest": {
        "annotated": "boolean",
        "name": "string",
        "oid": "string",
        "ref": "string"
      },
      "repository_root": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.tags'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "tags",
  "reference": "git.tags",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
