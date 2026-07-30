# git.tags

Inspect Git tags sorted by descending version refname. Each returned `oid` is the peeled target object id; for annotated tags this means the referenced object oid rather than the tag object oid. The `latest` output is the first matching item in that version-sorted order, not the newest tag by creation date.

Use this when a workflow needs Git state or Git side effects. In practice: inspect Git tags sorted by descending version refname. Each returned `oid` is the peeled target object id; for annotated tags this means the referenced object oid rather than the tag object oid. The `latest` output is the first matching item in that version-sorted order, not the newest tag by creation date.

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
  "match": "string | null",
  "match_kind": "'glob' | 'regex' | null"
}
```

## Outputs

```json
{
  "count": "integer",
  "items": [
    {
      "annotated": "boolean",
      "name": "string",
      "oid": "string",
      "ref": "string"
    }
  ],
  "latest": {
    "annotated": "boolean",
    "name": "string",
    "oid": "string",
    "ref": "string"
  },
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

### `git.tags`

```json
{
  "match": "v*",
  "match_kind": "glob"
}
```

### `git.tags`

```json
{
  "match": "^v?[0-9]+\\.[0-9]+\\.[0-9]+$",
  "match_kind": "regex"
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
          "match": "v*",
          "match_kind": "glob"
        },
        "reference": "git.tags"
      },
      {
        "inputs": {
          "match": "^v?[0-9]+\\.[0-9]+\\.[0-9]+$",
          "match_kind": "regex"
        },
        "reference": "git.tags"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {
      "match": "string | null",
      "match_kind": "'glob' | 'regex' | null"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "tags",
    "outputs": {
      "count": "integer",
      "items": [
        {
          "annotated": "boolean",
          "name": "string",
          "oid": "string",
          "ref": "string"
        }
      ],
      "latest": {
        "annotated": "boolean",
        "name": "string",
        "oid": "string",
        "ref": "string"
      },
      "repository_root": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Inspect Git tags sorted by descending version refname. Each returned `oid` is the peeled target object id; for annotated tags this means the referenced object oid rather than the tag object oid. The `latest` output is the first matching item in that version-sorted order, not the newest tag by creation date.",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "tags",
  "reference": "git.tags",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
