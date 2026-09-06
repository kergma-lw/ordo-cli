# gh.issue.comment.add

Add a comment to a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: add a comment to a GitHub issue.

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
  "comment_id": "string",
  "issue_ref": "string",
  "url": "string"
}
```

## Effects

- add GitHub issue comment

## Failure modes

- `issue_not_found`
- `body_invalid`
- `comment_blocked`

## Requirements

- None

## Example inputs

### `gh.issue.comment.add`

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
      "add GitHub issue comment"
    ],
    "examples": [
      {
        "inputs": {
          "body": "string",
          "issue_number": "integer",
          "repository": "string"
        },
        "reference": "gh.issue.comment.add"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "body_invalid",
      "comment_blocked"
    ],
    "inputs": {
      "body": "string",
      "issue_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.comment.add",
    "outputs": {
      "body": "string",
      "comment_id": "string",
      "issue_ref": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.comment.add'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.comment.add",
  "reference": "gh.issue.comment.add",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
