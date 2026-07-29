# gh.issue

Read a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: read a GitHub issue.

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
  "repository": "string"
}
```

## Outputs

```json
{
  "assignees": [
    "object"
  ],
  "author": "object",
  "body": "string",
  "closed": "boolean",
  "closed_at": "string",
  "comments": "object",
  "created_at": "string",
  "id": "string",
  "labels": [
    "object"
  ],
  "milestone": "object",
  "number": "number",
  "project_items": [
    "object"
  ],
  "reaction_groups": [
    "object"
  ],
  "repository": "object",
  "state": "string",
  "state_reason": "string",
  "title": "string",
  "updated_at": "string",
  "url": "string"
}
```

## Effects

- None

## Failure modes

- `issue_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.issue`

```json
{
  "issue_number": "integer",
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
    "effects": [],
    "examples": [
      {
        "inputs": {
          "issue_number": "integer",
          "repository": "string"
        },
        "reference": "gh.issue"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "probe_failed"
    ],
    "inputs": {
      "issue_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "issue",
    "outputs": {
      "assignees": [
        "object"
      ],
      "author": "object",
      "body": "string",
      "closed": "boolean",
      "closed_at": "string",
      "comments": "object",
      "created_at": "string",
      "id": "string",
      "labels": [
        "object"
      ],
      "milestone": "object",
      "number": "number",
      "project_items": [
        "object"
      ],
      "reaction_groups": [
        "object"
      ],
      "repository": "object",
      "state": "string",
      "state_reason": "string",
      "title": "string",
      "updated_at": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'gh.issue'",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "issue",
  "reference": "gh.issue",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
