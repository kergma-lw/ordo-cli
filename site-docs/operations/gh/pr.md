# gh.pr

Read pull request metadata from GitHub.

Use this when a workflow needs to inspect or change GitHub state. In practice: read pull request metadata from GitHub.

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
  "pull_number": "integer",
  "repository": "string"
}
```

## Outputs

```json
{
  "additions": "integer",
  "author": "object",
  "base_ref": "string",
  "body": "string",
  "changed_files": "integer",
  "commits_count": "integer",
  "created_at": "string",
  "deletions": "integer",
  "draft": "boolean",
  "head_ref": "string",
  "head_sha": "string",
  "mergeable": "boolean",
  "mergeable_state": "string",
  "number": "integer",
  "repository": "string",
  "review_decision": "string",
  "state": "string",
  "title": "string",
  "updated_at": "string",
  "url": "string"
}
```

## Effects

- None

## Failure modes

- `pull_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.pr`

```json
{
  "pull_number": 42
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
          "pull_number": 42
        },
        "reference": "gh.pr"
      }
    ],
    "failure_modes": [
      "pull_not_found",
      "probe_failed"
    ],
    "inputs": {
      "pull_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "pr",
    "outputs": {
      "additions": "integer",
      "author": "object",
      "base_ref": "string",
      "body": "string",
      "changed_files": "integer",
      "commits_count": "integer",
      "created_at": "string",
      "deletions": "integer",
      "draft": "boolean",
      "head_ref": "string",
      "head_sha": "string",
      "mergeable": "boolean",
      "mergeable_state": "string",
      "number": "integer",
      "repository": "string",
      "review_decision": "string",
      "state": "string",
      "title": "string",
      "updated_at": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read normalized metadata from a GitHub pull request.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr",
  "reference": "gh.pr",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
