# gh.issue.close

Close a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: close a GitHub issue.

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
  "repository": "string"
}
```

## Outputs

```json
{
  "closed": "boolean",
  "issue_ref": "string",
  "state": "string"
}
```

## Effects

- close GitHub issue

## Failure modes

- `issue_not_found`
- `close_blocked`

## Requirements

- None

## Example inputs

### `gh.issue.close`

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
    "effects": [
      "close GitHub issue"
    ],
    "examples": [
      {
        "inputs": {
          "issue_number": "integer",
          "repository": "string"
        },
        "reference": "gh.issue.close"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "close_blocked"
    ],
    "inputs": {
      "issue_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.close",
    "outputs": {
      "closed": "boolean",
      "issue_ref": "string",
      "state": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.close'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.close",
  "reference": "gh.issue.close",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
