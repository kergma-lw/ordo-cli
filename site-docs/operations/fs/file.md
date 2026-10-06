# Filesystem file

You need one file's content and metadata inside workflow logic, guards, or later adapters.

Observe UTF-8 content and metadata from one regular file without publishing its content by default.

## Use when

- `path`: required; supply the regular-file path explicitly. The result preserves the path text you supplied rather than replacing it with a resolved filesystem location. Publish basename, size, or line_count rather than full content by default; later workflow steps and adapters can use the returned content.
- The final path entry must identify a regular file with readable UTF-8 content. If that final entry is a symlink, the probe rejects it instead of reading its target. Missing, unreadable, non-file, and unsupported-content cases stop the probe without publishing partial content.
- The observation protects the final file entry while it is opened, but it is not an atomic snapshot of a path that may change concurrently. Symlinks in parent directories may still be traversed.

## What to provide

- `path`: required; provide one non-empty path to a readable UTF-8 regular file.

## Result and boundary

- Later steps can use `path`, `basename`, `filename_without_extension`, `extension`, `exists`, `kind`, `content`, `size`, `owner`, `group`, `permissions`, `modified_at`, and `line_count` from the same opened file.
- Missing, unreadable, non-file, or non-UTF-8 targets fail without partial content. A final symlink is rejected, while a symlink in a parent directory may be traversed. This is not an atomic snapshot: the path can change concurrently, and hardlinks may still refer to the same file.

## Do not use for

- Directory inspection or generic filesystem traversal; this probe requires one regular file path.
- Binary or non-UTF-8 content when canonical text content cannot be produced reliably.
- Atomic snapshots, workspace confinement, or general filesystem security isolation. The final entry cannot be a symlink, but parent-directory symlinks and hardlinks remain allowed.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.fs`: Parent filesystem connector family
- [`operations`](../../topics/operations.md): Catalog of published operations to check for a narrower supported surface
- `ordo-help describe workflow.local_expression.adapter.key_value`: One downstream adapter family that can project structured values from fs.file content

## Examples

- fs.file with inputs {"path": "/workspace/app.env"}

## Inspect next

- workflow.local_expression.adapter.key_value
- operations

## Exact machine contract

Use `ordo-help operation fs.file --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### fs_file_observation_steps

Supply file_path, register the fs.file probe, and publish basename, byte size, line count, and content-derived character count without publishing full content. The length filter counts characters, not lines.

```yaml
  - name: Inspect file
    uses: fs.file
    with:
      path: inputs.file_path
    register: inspected
  - name: Publish file summary
    publish:
      basename: step.inspected.outputs.basename
      size: step.inspected.outputs.size
      line_count: step.inspected.outputs.line_count
      character_count: step.inspected.outputs.content | length
```
### fs_file_observation_workflow

A complete observer workflow requires file_path and publishes a summary rather than full content. Content and metadata come from one observed file, not an atomic snapshot.

```yaml
version: 0
workflow: fs-file-inspection
inputs:
  file_path:
    description: Explicit path to a UTF-8 regular file; no real-file default.
blocks:
- steps:
  # Inspect the file and publish its summary.
  - name: Inspect file
    uses: fs.file
    with:
      path: inputs.file_path
    register: inspected
  - name: Publish file summary
    publish:
      basename: step.inspected.outputs.basename
      size: step.inspected.outputs.size
      line_count: step.inspected.outputs.line_count
      character_count: step.inspected.outputs.content | length
```
