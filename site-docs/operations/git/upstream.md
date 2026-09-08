# git.upstream

Read the current branch's exact configured remote, including nested names, and local remote-tracking branch tail, not the source-side branch name.

Use this when a workflow needs Git state or Git side effects. In practice: read the current branch's exact configured remote, including nested names, and local remote-tracking branch tail, not the source-side branch name.

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
  "branch": "string | null",
  "configured": "boolean",
  "remote": "string | null",
  "remote_branch": "string | null",
  "repository_root": "string",
  "upstream_ref": "string | null"
}
```

## Effects

- None

## Failure modes

- `probe_failed`

## Requirements

- None

## Example inputs

### `git.upstream`

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
        "reference": "git.upstream"
      }
    ],
    "failure_modes": [
      "probe_failed"
    ],
    "inputs": {},
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "upstream",
    "outputs": {
      "branch": "string | null",
      "configured": "boolean",
      "remote": "string | null",
      "remote_branch": "string | null",
      "repository_root": "string",
      "upstream_ref": "string | null"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Inspect the exact configured upstream remote, including nested names, and its conventional local tracking-tail branch",
    "tags": [
      "git",
      "probe"
    ]
  },
  "operation_name": "upstream",
  "reference": "git.upstream",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
