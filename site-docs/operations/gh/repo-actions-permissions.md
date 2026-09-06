# gh.repo.actions.permissions

Read GitHub Actions permissions for one repository.

Use this when a workflow needs to inspect or change GitHub state. In practice: read GitHub Actions permissions for one repository.

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
  "allowed_actions": "string | null",
  "enabled": "boolean",
  "repository": "string",
  "sha_pinning_required": "boolean | null"
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

### `gh.repo.actions.permissions`

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
        "reference": "gh.repo.actions.permissions"
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
    "name": "repo.actions.permissions",
    "outputs": {
      "allowed_actions": "string | null",
      "enabled": "boolean",
      "repository": "string",
      "sha_pinning_required": "boolean | null"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read GitHub Actions permissions for one repository.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "repo.actions.permissions",
  "reference": "gh.repo.actions.permissions",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
