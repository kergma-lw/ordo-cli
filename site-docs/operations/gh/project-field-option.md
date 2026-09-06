# gh.project.field.option

Check whether a GitHub Project field exposes a named option.

Use this when a workflow needs to inspect or change GitHub state. In practice: check whether a GitHub Project field exposes a named option.

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
  "option": "string",
  "project_id": "string"
}
```

## Outputs

```json
{
  "exists": "boolean"
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

### `gh.project.field.option`

```json
{
  "field": "string",
  "option": "string",
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
          "option": "string",
          "project_id": "string"
        },
        "reference": "gh.project.field.option"
      }
    ],
    "failure_modes": [
      "project_not_found",
      "probe_failed"
    ],
    "inputs": {
      "field": "string",
      "option": "string",
      "project_id": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "project.field.option",
    "outputs": {
      "exists": "boolean"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Return whether one named allowed value exists in one GitHub Project field when that field exposes a selectable value set",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "project.field.option",
  "reference": "gh.project.field.option",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
