# gh.project.field

Read metadata for a GitHub Project field.

Use this when a workflow needs to inspect or change GitHub state. In practice: read metadata for a GitHub Project field.

- Namespace: `gh`
- Kind: `probe`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "field": "string",
  "project_id": "string"
}
```

## Outputs

```json
{
  "exists": "boolean",
  "kind": "string",
  "name": "string",
  "options": [
    "string"
  ]
}
```

## Effects

- None

## Failure modes

- `project_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.project.field`

```json
{
  "field": "string",
  "project_id": "string"
}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [
      "host",
      "viewer",
      "scopes",
      "repository"
    ],
    "prerequisites": [
      "gh binary available",
      "GitHub auth available"
    ]
  },
  "document_kind": "operation",
  "namespace": "gh",
  "operation": {
    "deprecated": false,
    "effects": [],
    "examples": [
      {
        "inputs": {
          "field": "string",
          "project_id": "string"
        },
        "reference": "gh.project.field"
      }
    ],
    "failure_modes": [
      "project_not_found",
      "probe_failed"
    ],
    "inputs": {
      "field": "string",
      "project_id": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "project.field",
    "outputs": {
      "exists": "boolean",
      "kind": "string",
      "name": "string",
      "options": [
        "string"
      ]
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'gh.project.field'",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "project.field",
  "reference": "gh.project.field",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
