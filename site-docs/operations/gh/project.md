# gh.project

Read a GitHub Project.

Use this when a workflow needs to inspect or change GitHub state. In practice: read a GitHub Project.

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
  "project_id": "string"
}
```

## Outputs

```json
{
  "exists": "boolean",
  "id": "string",
  "title": "string"
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

### `gh.project`

```json
{
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
          "project_id": "string"
        },
        "reference": "gh.project"
      }
    ],
    "failure_modes": [
      "project_not_found",
      "probe_failed"
    ],
    "inputs": {
      "project_id": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "project",
    "outputs": {
      "exists": "boolean",
      "id": "string",
      "title": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'gh.project'",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "project",
  "reference": "gh.project",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
