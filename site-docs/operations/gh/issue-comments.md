# gh.issue.comments

Read comments from a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: read comments from a GitHub issue.

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
  "limit": "integer",
  "repository": "string"
}
```

## Outputs

```json
{
  "comments": [
    "object"
  ],
  "issue_ref": "string",
  "total_count": "number"
}
```

## Effects

- None

## Failure modes

- `issue_not_found`
- `limit_invalid`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.issue.comments`

```json
{
  "issue_number": "integer",
  "limit": "integer",
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
          "limit": "integer",
          "repository": "string"
        },
        "reference": "gh.issue.comments"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "limit_invalid",
      "probe_failed"
    ],
    "inputs": {
      "issue_number": "integer",
      "limit": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "issue.comments",
    "outputs": {
      "comments": [
        "object"
      ],
      "issue_ref": "string",
      "total_count": "number"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'gh.issue.comments'",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "issue.comments",
  "reference": "gh.issue.comments",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
