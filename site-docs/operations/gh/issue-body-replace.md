# gh.issue.body.replace

Replace a GitHub issue body.

Use this when a workflow needs to inspect or change GitHub state. In practice: replace a GitHub issue body.

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
  "body": "string",
  "issue_number": "integer",
  "repository": "string"
}
```

## Outputs

```json
{
  "body": "string",
  "changed": "boolean",
  "issue_ref": "string",
  "url": "string"
}
```

## Effects

- replace GitHub issue body

## Failure modes

- `issue_not_found`
- `body_invalid`
- `replace_blocked`

## Requirements

- None

## Example inputs

### `gh.issue.body.replace`

```json
{
  "body": "string",
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
      "replace GitHub issue body"
    ],
    "examples": [
      {
        "inputs": {
          "body": "string",
          "issue_number": "integer",
          "repository": "string"
        },
        "reference": "gh.issue.body.replace"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "body_invalid",
      "replace_blocked"
    ],
    "inputs": {
      "body": "string",
      "issue_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.body.replace",
    "outputs": {
      "body": "string",
      "changed": "boolean",
      "issue_ref": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.body.replace'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.body.replace",
  "reference": "gh.issue.body.replace",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
