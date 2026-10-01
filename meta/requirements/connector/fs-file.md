# Filesystem file probe requirements

## Role

- `fs.file` is the public `fs` connector probe for observing one filesystem path as one file snapshot.

## Required question

- The probe must answer what file snapshot is observed at one requested path.

## Required input

- `path` is required.
- `path` must be a non-empty string.

## Output contract

- A successful result must return structured file-snapshot fields rather than raw transport text.
- The MVP output shape must include at least:
  - `path`
  - `exists`
  - `kind`
  - `content`
- The probe must expose these path-derived file metadata projections:
  - `basename`
  - `filename_without_extension`
  - `extension`
- The MVP may additionally expose file-snapshot metadata that belongs naturally to the same observed file, for example:
  - `size`
  - `owner`
  - `group`
  - `permissions`
  - `modified_at`
  - `line_count`

## Snapshot semantics

- `content` is part of the probe contract rather than an optional side channel.
- `kind` must describe filesystem-entry kind rather than content classification.
- `kind` must not depend on the external `file` utility or on MIME/magic classification heuristics.
- `basename`, `filename_without_extension`, and `extension` must be derived from the resolved file path rather than from raw user input spelling.
- `extension` must use the final basename suffix after the last dot and must not include the dot.
- `line_count`, when exposed, is derived from `content`.

## Secure observation semantics

- The initial no-follow stat preserves existing missing-path, stat-failure, and nonregular-entry diagnostics; it is not a security barrier.
- Opening requires nonzero integer `O_NOFOLLOW` and `O_NONBLOCK` capabilities. If either is unavailable, return `content_unavailable` with `probe.fs_file.secure_open_unavailable`; there must be no unsafe fallback.
- Validate the opened descriptor with `fstat` as a regular file before reading. Content and metadata must come from that same descriptor, not a later pathname lookup.
- A final path entry that is a symlink is rejected as `not_a_file` rather than followed. An opened FIFO or directory also returns `not_a_file`. Open-stage errors including `ELOOP` return `content_unavailable` without guessing entry kind; `ELOOP` can also describe a parent loop.
- Descriptor-stat failure returns `probe_failed` with `probe.fs_file.stat_failed`.
- Same-descriptor observation is not an atomic snapshot under concurrent writes. Relative and absolute textual `Path` projections do not identify the resolved opened object.
- Symlinks in parent directories and hardlinks remain allowed. This is not workspace confinement, device-open sandboxing, protection against parent mutation, or same-UID isolation.
- POSIX race tests establish only their tested scope; do not claim Windows test coverage or platform guarantees from them.

## Failure statuses

- Missing paths must fail explicitly as `path_not_found`.
- Non-file paths must fail explicitly as `not_a_file`.
- Content-read or content-decode failures must fail explicitly as `content_unavailable`.
- Any remaining implementation-local breakdown must normalize to `probe_failed`.

## Boundary contract

- The probe must stay focused on one path and one file snapshot.
- The probe must not absorb tree search, directory listing, config parsing, content classification, or mutation semantics.
- The probe must not become a generic filesystem API bundle.
- The probe must not expand into dirname, join, slugify, or traversal helper semantics.

## Discovery rule

- The public contract should be discoverable through `ordo-help operation fs.file`.
- Discovery material should make clear that `fs.file` is the canonical public filesystem read probe in the MVP.
