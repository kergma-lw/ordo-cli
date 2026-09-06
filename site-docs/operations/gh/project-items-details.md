# gh.project.items.details

Return normalized GitHub Project items with stable content details

Use this when a workflow needs to inspect or change GitHub state. In practice: return normalized GitHub Project items with stable content details.

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
      "label_names": [
        "string"
      ],
      "number": "integer",
      "repository": "string",
      "state": "string",
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

### `gh.project.items.details`

```json
{
  "content_kind": "Issue",
  "project_id": "PVT_demo"
}
```

### `gh.project.items.details`

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
          "content_kind": "Issue",
          "project_id": "PVT_demo"
        },
        "reference": "gh.project.items.details",
        "why": "Load project-scoped issue details including state and labels."
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
        "reference": "gh.project.items.details",
        "why": "Load detailed facts for one explicit subset of project-backed GitHub content."
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
    "name": "project.items.details",
    "outputs": {
      "count": "integer",
      "items": [
        {
          "content_kind": "string",
          "item_id": "string",
          "label_names": [
            "string"
          ],
          "number": "integer",
          "repository": "string",
          "state": "string",
          "title": "string",
          "url": "string"
        }
      ]
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Return normalized GitHub Project items with stable content details",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "project.items.details",
  "reference": "gh.project.items.details",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
