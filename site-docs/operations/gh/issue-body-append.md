# gh.issue.body.append

Append text to a GitHub issue body.

Use this when a workflow needs to inspect or change GitHub state. In practice: append text to a GitHub issue body.

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
  "repository": "string",
  "separator": "string | null",
  "text": "string"
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

- append text to GitHub issue body

## Failure modes

- `issue_not_found`
- `text_invalid`
- `append_blocked`

## Requirements

- None

## Example inputs

### `gh.issue.body.append`

```json
{
  "issue_number": "integer",
  "repository": "string",
  "separator": "string | null",
  "text": "string"
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
      "append text to GitHub issue body"
    ],
    "examples": [
      {
        "inputs": {
          "issue_number": "integer",
          "repository": "string",
          "separator": "string | null",
          "text": "string"
        },
        "reference": "gh.issue.body.append"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "text_invalid",
      "append_blocked"
    ],
    "inputs": {
      "issue_number": "integer",
      "repository": "string",
      "separator": "string | null",
      "text": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.body.append",
    "outputs": {
      "body": "string",
      "changed": "boolean",
      "issue_ref": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.body.append'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.body.append",
  "reference": "gh.issue.body.append",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
