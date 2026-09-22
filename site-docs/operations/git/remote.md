# git.remote

Inspect a configured remote's effective fetch and push URLs and mirror setting without network access. Git applies URL rewrites; returned URLs are preserved verbatim. An absent remote has exists=false, empty URL lists, and mirror=null.

Use this when a workflow needs Git state or Git side effects. In practice: inspect a configured remote's effective fetch and push URLs and mirror setting without network access. Git applies URL rewrites; returned URLs are preserved verbatim. An absent remote has exists=false, empty URL lists, and mirror=null.

- Namespace: `git`
- Kind: `probe`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "remote": "string"
}
```

## Outputs

```json
{
  "exists": "boolean",
  "fetch_urls": [
    "string"
  ],
  "mirror": "boolean | null",
  "name": "string",
  "push_urls": [
    "string"
  ]
}
```

## Effects

- None

## Failure modes

- `probe_failed`

## Requirements

- None

## Example inputs

### `git.remote`

```json
{
  "remote": "string"
}
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
        "inputs": {
          "remote": "string"
        },
        "reference": "git.remote"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {
      "remote": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "remote",
    "outputs": {
      "exists": "boolean",
      "fetch_urls": [
        "string"
      ],
      "mirror": "boolean | null",
      "name": "string",
      "push_urls": [
        "string"
      ]
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Inspect a configured remote's effective fetch and push URLs and mirror setting without network access. Git applies URL rewrites; returned URLs are preserved verbatim. An absent remote has exists=false, empty URL lists, and mirror=null.",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "remote",
  "reference": "git.remote",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
