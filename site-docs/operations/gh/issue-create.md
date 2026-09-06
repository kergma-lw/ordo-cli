# gh.issue.create

Create a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: create a GitHub issue.

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
  "body": "string | null",
  "repository": "string",
  "title": "string"
}
```

## Outputs

```json
{
  "issue_ref": "string",
  "number": "integer",
  "repository": "string",
  "title": "string",
  "url": "string"
}
```

## Effects

- create GitHub issue

## Failure modes

- `repository_not_found`
- `title_invalid`
- `create_blocked`

## Requirements

- None

## Invalidated observations

- `gh.issue`

## Example inputs

### `gh.issue.create`

```json
{
  "body": "string | null",
  "repository": "string",
  "title": "string"
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
      "create GitHub issue"
    ],
    "examples": [
      {
        "inputs": {
          "body": "string | null",
          "repository": "string",
          "title": "string"
        },
        "reference": "gh.issue.create"
      }
    ],
    "failure_modes": [
      "repository_not_found",
      "title_invalid",
      "create_blocked"
    ],
    "inputs": {
      "body": "string | null",
      "repository": "string",
      "title": "string"
    },
    "invalidates_observations": [
      "gh.issue"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.create",
    "outputs": {
      "issue_ref": "string",
      "number": "integer",
      "repository": "string",
      "title": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.create'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.create",
  "reference": "gh.issue.create",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
