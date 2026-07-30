# git.tag

Read one Git tag. The `oid` output is the object id resolved for the tag ref itself; for annotated tags this is the tag object's oid rather than the peeled target commit oid.

Use this when a workflow needs Git state or Git side effects. In practice: read one Git tag. The `oid` output is the object id resolved for the tag ref itself; for annotated tags this is the tag object's oid rather than the peeled target commit oid.

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
  "name": "string"
}
```

## Outputs

```json
{
  "annotated": "boolean | null",
  "exists": "boolean",
  "name": "string",
  "oid": "string | null",
  "ref": "string",
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

### `git.tag`

```json
{
  "name": "v1.2.3"
}
```

### `git.tag`

```json
{
  "name": "release-2026-07"
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
          "name": "v1.2.3"
        },
        "reference": "git.tag"
      },
      {
        "inputs": {
          "name": "release-2026-07"
        },
        "reference": "git.tag"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {
      "name": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "tag",
    "outputs": {
      "annotated": "boolean | null",
      "exists": "boolean",
      "name": "string",
      "oid": "string | null",
      "ref": "string",
      "repository_root": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read one Git tag. The `oid` output is the object id resolved for the tag ref itself; for annotated tags this is the tag object's oid rather than the peeled target commit oid.",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "tag",
  "reference": "git.tag",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
