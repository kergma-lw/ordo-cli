# gh.repo

Read normalized GitHub repository identity and fork facts.

Use this when a workflow needs to inspect or change GitHub state. In practice: read normalized GitHub repository identity and fork facts.

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
  "repository": "string"
}
```

## Outputs

```json
{
  "archived": "boolean",
  "default_branch": "string | null",
  "id": "string",
  "is_fork": "boolean",
  "parent_repository": "string | null",
  "repository": "string"
}
```

## Effects

- None

## Failure modes

- `repository_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.repo`

```json
{}
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
        "inputs": {},
        "reference": "gh.repo"
      }
    ],
    "failure_modes": [
      "repository_not_found",
      "probe_failed"
    ],
    "inputs": {
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "repo",
    "outputs": {
      "archived": "boolean",
      "default_branch": "string | null",
      "id": "string",
      "is_fork": "boolean",
      "parent_repository": "string | null",
      "repository": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read normalized GitHub repository identity and fork facts.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "repo",
  "reference": "gh.repo",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
