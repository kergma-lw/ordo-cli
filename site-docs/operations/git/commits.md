# git.commits

Read a bounded list of Git commits.

Use this when a workflow needs Git state or Git side effects. In practice: read a bounded list of Git commits.

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
  "limit": "integer",
  "rev": "string"
}
```

## Outputs

```json
{
  "count": "integer",
  "items": [
    {
      "author_name": "string",
      "body": "string",
      "commit": "string",
      "committed_at": "string",
      "subject": "string",
      "text": "string"
    }
  ],
  "repository_root": "string",
  "rev": "string"
}
```

## Effects

- None

## Failure modes

- `probe_failed`

## Requirements

- None

## Example inputs

### `git.commits`

```json
{
  "limit": 5,
  "rev": "HEAD"
}
```

### `git.commits`

```json
{
  "limit": 3,
  "rev": "HEAD~10..HEAD"
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
          "limit": 5,
          "rev": "HEAD"
        },
        "reference": "git.commits"
      },
      {
        "inputs": {
          "limit": 3,
          "rev": "HEAD~10..HEAD"
        },
        "reference": "git.commits"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {
      "limit": "integer",
      "rev": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "commits",
    "outputs": {
      "count": "integer",
      "items": [
        {
          "author_name": "string",
          "body": "string",
          "commit": "string",
          "committed_at": "string",
          "subject": "string",
          "text": "string"
        }
      ],
      "repository_root": "string",
      "rev": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Return a bounded readable list of commit texts from one revision scope with only minimal metadata. rev accepts revisions and ranges such as HEAD~10..HEAD, not Git options; after trimming whitespace it must not start with '-'. This probe is intentionally narrow: it does not expose patch text, changed files, diff stats, graph decoration, or arbitrary git log formatting.",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "commits",
  "reference": "git.commits",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
