# git.stash

List Git stash entries.

Use this when a workflow needs Git state or Git side effects. In practice: list Git stash entries.

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
  "items": [
    {
      "name": "string",
      "selector": "string",
      "summary": "string"
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

### `git.stash`

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
        "reference": "git.stash"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {},
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "stash",
    "outputs": {
      "count": "integer",
      "items": [
        {
          "name": "string",
          "selector": "string",
          "summary": "string"
        }
      ],
      "repository_root": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'git.stash'",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "stash",
  "reference": "git.stash",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
