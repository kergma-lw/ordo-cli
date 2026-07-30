# gh.pr.checks

Read normalized status and check-run results from a GitHub pull request head.

Use this when a workflow needs to inspect or change GitHub state. In practice: read normalized status and check-run results from a GitHub pull request head.

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
  "checks": [
    {
      "conclusion": "string",
      "context": "string",
      "kind": "string",
      "name": "string",
      "status": "string",
      "url": "string"
    }
  ],
  "failed_count": "integer",
  "head_sha": "string",
  "overall_state": "string",
  "pending_count": "integer",
  "pull_ref": "string",
  "skipped_count": "integer",
  "success_count": "integer",
  "total_count": "integer"
}
```

## Effects

- None

## Failure modes

- `pull_not_found`
- `checks_unavailable`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.pr.checks`

```json
{
  "pull_number": "integer",
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
          "pull_number": "integer",
          "repository": "string"
        },
        "reference": "gh.pr.checks"
      }
    ],
    "failure_modes": [
      "pull_not_found",
      "checks_unavailable",
      "probe_failed"
    ],
    "inputs": {
      "pull_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "pr.checks",
    "outputs": {
      "checks": [
        {
          "conclusion": "string",
          "context": "string",
          "kind": "string",
          "name": "string",
          "status": "string",
          "url": "string"
        }
      ],
      "failed_count": "integer",
      "head_sha": "string",
      "overall_state": "string",
      "pending_count": "integer",
      "pull_ref": "string",
      "skipped_count": "integer",
      "success_count": "integer",
      "total_count": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read normalized status and check-run results from a GitHub pull request head.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr.checks",
  "reference": "gh.pr.checks",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
