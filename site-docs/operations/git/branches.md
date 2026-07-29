# git.branches

List local Git branches.

Use this when a workflow needs Git state or Git side effects. In practice: list local Git branches.

- Namespace: `git`
- Kind: `probe`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{}
```

## Outputs

```json
{
  "count": "integer",
  "current": "string | null",
  "items": [
    {
      "current": "boolean",
      "kind": "string",
      "name": "string",
      "ref": "string"
    }
  ],
  "repository_root": "string"
}
```

## Effects

- None

## Failure modes

- `probe_failed`

## Requirements

- None

## Example inputs

### `git.branches`

```json
{}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [
      "repository_root"
    ],
    "prerequisites": [
      "git binary available",
      "inside git repository"
    ]
  },
  "document_kind": "operation",
  "namespace": "git",
  "operation": {
    "deprecated": false,
    "effects": [],
    "examples": [
      {
        "inputs": {},
        "reference": "git.branches"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {},
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "branches",
    "outputs": {
      "count": "integer",
      "current": "string | null",
      "items": [
        {
          "current": "boolean",
          "kind": "string",
          "name": "string",
          "ref": "string"
        }
      ],
      "repository_root": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.branches'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "branches",
  "reference": "git.branches",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
