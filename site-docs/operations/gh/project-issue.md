# gh.project.issue

Read one issue's membership and field values in a GitHub Project.

Use this when a workflow needs to inspect or change GitHub state. In practice: read one issue's membership and field values in a GitHub Project.

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
  "issue_number": "integer",
  "project_id": "string",
  "repository": "string"
}
```

## Outputs

```json
{
  "estimate": "number",
  "exists": "boolean",
  "item_id": "string",
  "iteration": "string",
  "priority": "string",
  "size": "string",
  "status": "string",
  "type": "string"
}
```

## Effects

- None

## Failure modes

- `issue_not_found`
- `project_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.project.issue`

```json
{
  "issue_number": "integer",
  "project_id": "string",
  "repository": "string"
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
          "issue_number": "integer",
          "project_id": "string",
          "repository": "string"
        },
        "reference": "gh.project.issue"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "project_not_found",
      "probe_failed"
    ],
    "inputs": {
      "issue_number": "integer",
      "project_id": "string",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "project.issue",
    "outputs": {
      "estimate": "number",
      "exists": "boolean",
      "item_id": "string",
      "iteration": "string",
      "priority": "string",
      "size": "string",
      "status": "string",
      "type": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'gh.project.issue'",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "project.issue",
  "reference": "gh.project.issue",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
