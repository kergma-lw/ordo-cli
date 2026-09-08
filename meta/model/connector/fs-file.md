# Filesystem file probe model

## Public reference

- `fs.file`

## Kind

- `probe`

## Mental model

- This probe resolves one path into one file-oriented snapshot.
- It is the public `fs` read surface for file content and closely related file metadata.
- It is not a search probe, parser probe, or mutation surface.

## Input shape

- `path: string`

## Output shape

```json
{
  "path": "/workspace/app.env",
  "basename": "app.env",
  "filename_without_extension": "app",
  "extension": "env",
  "exists": true,
  "kind": "file",
  "content": "HOST=localhost\nPORT=5432\n",
  "size": 25,
  "owner": "ww",
  "group": "ww",
  "permissions": "0644",
  "modified_at": "2026-07-29T18:30:00Z",
  "line_count": 2
}
```

## Modeled semantics

- File snapshot means one opened regular-file descriptor for both content and `fstat` metadata, not atomic consistency under concurrent writes.
- The initial no-follow stat retains diagnostics. Nonzero integer `O_NOFOLLOW` and `O_NONBLOCK` are required; missing capabilities fail closed as `content_unavailable` / `probe.fs_file.secure_open_unavailable`.
- `fstat` must verify regular-file kind before reading the same descriptor. Opened FIFO/directory targets are `not_a_file`; open errors including `ELOOP` are `content_unavailable` without an inferred kind; descriptor-stat errors are `probe_failed` / `probe.fs_file.stat_failed`.
- Relative/absolute textual `Path` projections remain path-derived, not resolved descriptor identities. Parent symlinks and hardlinks remain allowed, without workspace confinement, device-open sandboxing, or same-UID isolation.

- `basename` is the last path segment from the resolved file path.
- `filename_without_extension` and `extension` are deterministic projections of `basename` using the last dot only.
- `extension` does not include the dot.
- `exists` reports whether the requested path resolved to an existing file snapshot in the success case.
- `kind` uses connector-owned filesystem-entry vocabulary rather than content-type or MIME vocabulary.
- `content` is the canonical payload of the snapshot rather than a raw-detail afterthought.
- `size`, `owner`, `group`, `permissions`, `modified_at`, and `line_count` are file-snapshot facts, not parsing or policy results.

## Basename split examples

- `foo.txt` → `basename=foo.txt`, `filename_without_extension=foo`, `extension=txt`
- `archive.tar.gz` → `basename=archive.tar.gz`, `filename_without_extension=archive.tar`, `extension=gz`
- `README` → `basename=README`, `filename_without_extension=README`, `extension=""`
- `.env` → `basename=.env`, `filename_without_extension=""`, `extension=env`

## Failure model

- `path_not_found` means the requested path did not resolve to an existing entry.
- `not_a_file` means the path resolved to an entry that the probe does not treat as a file snapshot target.
- `content_unavailable` means the path resolved but the connector could not produce the required content field.
- `probe_failed` remains the residual normalized failure for other local breakdown.

## Boundary model

- The probe owns one file snapshot only.
- It does not own:
  - directory enumeration;
  - tree search;
  - format parsing;
  - MIME/magic classification;
  - file mutation.
