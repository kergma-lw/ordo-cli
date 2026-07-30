# gh.project.items

Read normalized items from a GitHub Project.

Use this when a workflow needs to inspect or change GitHub state. In practice: read normalized items from a GitHub Project.

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
  "content_kind": "string",
  "content_refs": [
    "string"
  ],
  "filters": [
    {
      "field": "string",
      "value": "scalar"
    }
  ],
  "project_id": "string"
}
```

## Outputs

```json
{
  "count": "integer",
  "items": [
    {
      "content_kind": "string",
      "item_id": "string",
      "number": "integer",
      "repository": "string",
      "title": "string",
      "url": "string"
    }
  ]
}
```

## Effects

- None

## Failure modes

- `project_not_found`
- `unknown_field`
- `ambiguous_field`
- `unsupported_field_type`
- `invalid_filter_value`
- `invalid_content_ref`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.project.items`

```json
{
  "project_id": "PVT_demo"
}
```

### `gh.project.items`

```json
{
  "content_kind": "Issue",
  "filters": [
    {
      "field": "Status",
      "value": "Ready"
    }
  ],
  "project_id": "PVT_demo"
}
```

### `gh.project.items`

```json
{
  "content_kind": "Issue",
  "content_refs": [
    "owner/repo#7",
    "owner/repo#8"
  ],
  "filters": [
    {
      "field": "Type",
      "value": "Task"
    }
  ],
  "project_id": "PVT_demo"
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
    "effects": [],
    "examples": [
      {
        "inputs": {
          "project_id": "PVT_demo"
        },
        "reference": "gh.project.items",
        "why": "Load normalized project membership facts without mutating project state."
      },
      {
        "inputs": {
          "content_kind": "Issue",
          "filters": [
            {
              "field": "Status",
              "value": "Ready"
            }
          ],
          "project_id": "PVT_demo"
        },
        "reference": "gh.project.items",
        "why": "Narrow one project scan to issue-like items whose Status field equals Ready."
      },
      {
        "inputs": {
          "content_kind": "Issue",
          "content_refs": [
            "owner/repo#7",
            "owner/repo#8"
          ],
          "filters": [
            {
              "field": "Type",
              "value": "Task"
            }
          ],
          "project_id": "PVT_demo"
        },
        "reference": "gh.project.items",
        "why": "Intersect one project item query with one explicit set of GitHub content references."
      }
    ],
    "failure_modes": [
      "project_not_found",
      "unknown_field",
      "ambiguous_field",
      "unsupported_field_type",
      "invalid_filter_value",
      "invalid_content_ref",
      "probe_failed"
    ],
    "inputs": {
      "content_kind": "string",
      "content_refs": [
        "string"
      ],
      "filters": [
        {
          "field": "string",
          "value": "scalar"
        }
      ],
      "project_id": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "project.items",
    "outputs": {
      "count": "integer",
      "items": [
        {
          "content_kind": "string",
          "item_id": "string",
          "number": "integer",
          "repository": "string",
          "title": "string",
          "url": "string"
        }
      ]
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Return normalized GitHub Project items for one project membership scan",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "project.items",
  "reference": "gh.project.items",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
