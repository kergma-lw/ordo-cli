# gh.project.issue.field_single_select.set

Set a single-select field for a GitHub Project issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: set a single-select field for a GitHub Project issue.

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
  "field": "string",
  "issue_number": "integer",
  "option": "string",
  "project_id": "string",
  "repository": "string"
}
```

## Outputs

```json
{
  "changed": "boolean",
  "field": "string",
  "issue_ref": "string",
  "item_id": "string",
  "option": "string",
  "project_id": "string"
}
```

## Effects

- set one GitHub project issue single-select field by field name

## Failure modes

- `issue_not_found`
- `project_not_found`
- `field_not_found`
- `field_kind_unsupported`
- `option_not_found`
- `field_update_blocked`

## Requirements

- None

## Preflight observations

```json
[
  {
    "fields": [
      "exists"
    ],
    "probe": "gh.project.issue",
    "with": {
      "issue_number": "{issue_number}",
      "project_id": "{project_id}",
      "repository": "{repository}"
    }
  },
  {
    "fields": [
      "exists"
    ],
    "probe": "gh.project.field",
    "with": {
      "field": "{field}",
      "project_id": "{project_id}"
    }
  },
  {
    "fields": [
      "exists"
    ],
    "probe": "gh.project.field.option",
    "with": {
      "field": "{field}",
      "option": "{option}",
      "project_id": "{project_id}"
    }
  }
]
```

## Invalidated observations

- `gh.project.issue`

## Example inputs

### `gh.project.issue.field_single_select.set`

```json
{
  "field": "string",
  "issue_number": "integer",
  "option": "string",
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
    "effects": [
      "set one GitHub project issue single-select field by field name"
    ],
    "examples": [
      {
        "inputs": {
          "field": "string",
          "issue_number": "integer",
          "option": "string",
          "project_id": "string",
          "repository": "string"
        },
        "reference": "gh.project.issue.field_single_select.set"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "project_not_found",
      "field_not_found",
      "field_kind_unsupported",
      "option_not_found",
      "field_update_blocked"
    ],
    "inputs": {
      "field": "string",
      "issue_number": "integer",
      "option": "string",
      "project_id": "string",
      "repository": "string"
    },
    "invalidates_observations": [
      "gh.project.issue"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "project.issue.field_single_select.set",
    "outputs": {
      "changed": "boolean",
      "field": "string",
      "issue_ref": "string",
      "item_id": "string",
      "option": "string",
      "project_id": "string"
    },
    "preflight_observations": [
      {
        "fields": [
          "exists"
        ],
        "probe": "gh.project.issue",
        "with": {
          "issue_number": "{issue_number}",
          "project_id": "{project_id}",
          "repository": "{repository}"
        }
      },
      {
        "fields": [
          "exists"
        ],
        "probe": "gh.project.field",
        "with": {
          "field": "{field}",
          "project_id": "{project_id}"
        }
      },
      {
        "fields": [
          "exists"
        ],
        "probe": "gh.project.field.option",
        "with": {
          "field": "{field}",
          "option": "{option}",
          "project_id": "{project_id}"
        }
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.project.issue.field_single_select.set'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "project.issue.field_single_select.set",
  "reference": "gh.project.issue.field_single_select.set",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
