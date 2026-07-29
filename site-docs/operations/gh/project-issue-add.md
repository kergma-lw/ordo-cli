# gh.project.issue.add

Add a GitHub issue to a GitHub Project.

Use this when a workflow needs to inspect or change GitHub state. In practice: add a GitHub issue to a GitHub Project.

- Namespace: `gh`
- Kind: `action`
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
  "added": "boolean",
  "issue_ref": "string",
  "item_id": "string",
  "project_id": "string"
}
```

## Effects

- add GitHub issue to project

## Failure modes

- `issue_not_found`
- `project_not_found`
- `add_blocked`

## Requirements

- None

## Invalidated observations

- `gh.project.issue`

## Example inputs

### `gh.project.issue.add`

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
      "scopes"
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
    "effects": [
      "add GitHub issue to project"
    ],
    "examples": [
      {
        "inputs": {
          "issue_number": "integer",
          "project_id": "string",
          "repository": "string"
        },
        "reference": "gh.project.issue.add"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "project_not_found",
      "add_blocked"
    ],
    "inputs": {
      "issue_number": "integer",
      "project_id": "string",
      "repository": "string"
    },
    "invalidates_observations": [
      "gh.project.issue"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "project.issue.add",
    "outputs": {
      "added": "boolean",
      "issue_ref": "string",
      "item_id": "string",
      "project_id": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.project.issue.add'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "project.issue.add",
  "reference": "gh.project.issue.add",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
