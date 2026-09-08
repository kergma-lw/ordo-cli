# fs.file

Read canonical content and metadata from the same opened regular file, without atomic snapshot guarantees.

Use this when a workflow needs this exact operation surface. In practice: read canonical content and metadata from the same opened regular file, without atomic snapshot guarantees.

- Namespace: `fs`
- Kind: `probe`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "path": "string"
}
```

## Outputs

```json
{
  "basename": "string",
  "content": "string",
  "exists": "boolean",
  "extension": "string",
  "filename_without_extension": "string",
  "group": "string",
  "kind": "string",
  "line_count": "integer",
  "modified_at": "string",
  "owner": "string",
  "path": "string",
  "permissions": "string",
  "size": "integer"
}
```

## Authoring contract

Observe UTF-8 content and metadata from the same opened regular file. The initial no-follow stat preserves diagnostics; nonzero O_NOFOLLOW and O_NONBLOCK are required before opening, then fstat verifies a regular file before reading that descriptor.

- You need one file's content and metadata inside workflow logic, guards, or later adapters.
- Supply a required path explicitly. Relative and absolute textual Path projections are retained, not resolved to the opened object's identity. Publish basename, size, or line_count rather than full content by default; later adapters can consume the registered content.
- Initial missing paths return path_not_found; initial final symlinks or nonregular entries and opened FIFO/directory objects return not_a_file. Missing secure flags return content_unavailable with probe.fs_file.secure_open_unavailable and no fallback. Open errors including ELOOP return content_unavailable without guessing kind; fstat failure returns probe_failed with probe.fs_file.stat_failed.

### Boundaries

- Directory inspection or generic filesystem traversal; this probe requires one regular file path.
- Binary or non-UTF-8 content when canonical text content cannot be produced reliably.
- Atomic snapshots under concurrent writes, workspace confinement, device-open sandboxing, or same-UID isolation. Parent symlinks and hardlinks remain allowed; POSIX race tests do not establish Windows support.

### fs_file_observation_steps

Supply file_path, register the fs.file probe, and publish basename, byte size, line count, and content-derived character count without publishing full content. The length filter counts characters, not lines. Runner verification validates schema/fixture form only, not file access or race safety.

```yaml
  - name: inspect-file
    uses: fs.file
    with:
      path: inputs.file_path
    register: inspected
  - name: summarize-file
    publish:
      basename: step.inspected.outputs.basename
      size: step.inspected.outputs.size
      line_count: step.inspected.outputs.line_count
      character_count: step.inspected.outputs.content | length
```

### fs_file_observation_workflow

A complete observer workflow requires file_path with no real-file default and publishes a summary rather than full content. Content and metadata come from one validated descriptor, not an atomic snapshot. Runner verification checks schema/fixture form without opening files; POSIX race tests are separate evidence.

```yaml
version: 0
workflow: fs-file-inspection
inputs:
  file_path:
    description: Explicit path to a UTF-8 regular file; no real-file default.
blocks:
- steps:
  - name: inspect-file
    uses: fs.file
    with:
      path: inputs.file_path
    register: inspected
  - name: summarize-file
    publish:
      basename: step.inspected.outputs.basename
      size: step.inspected.outputs.size
      line_count: step.inspected.outputs.line_count
      character_count: step.inspected.outputs.content | length
```

## Effects

- None

## Failure modes

- `path_not_found`
- `not_a_file`
- `content_unavailable`
- `probe_failed`

## Requirements

- None

## Example inputs

### `fs.file`

```json
{
  "path": "/workspace/app.env"
}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [],
    "prerequisites": []
  },
  "document_kind": "operation",
  "namespace": "fs",
  "operation": {
    "deprecated": false,
    "effects": [],
    "examples": [
      {
        "inputs": {
          "path": "/workspace/app.env"
        },
        "reference": "fs.file"
      }
    ],
    "failure_modes": [
      "path_not_found",
      "not_a_file",
      "content_unavailable",
      "probe_failed"
    ],
    "inputs": {
      "path": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "file",
    "outputs": {
      "basename": "string",
      "content": "string",
      "exists": "boolean",
      "extension": "string",
      "filename_without_extension": "string",
      "group": "string",
      "kind": "string",
      "line_count": "integer",
      "modified_at": "string",
      "owner": "string",
      "path": "string",
      "permissions": "string",
      "size": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read canonical content and metadata from the same opened regular file, without atomic snapshot guarantees.",
    "tags": [
      "fs",
      "probe"
    ]
  },
  "operation_name": "file",
  "reference": "fs.file",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
