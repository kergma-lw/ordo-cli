"""Read content and metadata from the same opened regular file, not atomically.

The initial no-follow stat preserves diagnostics, but is not a security barrier.
Safe-open flags reject final symlink swaps and avoid blocking on FIFO swaps;
fstat validates the opened object and supplies all metadata. Open failures,
including ELOOP (which can also mean a parent loop), are content_unavailable.
Missing safe-open flags fail diagnostically without an unsafe fallback.
Parent symlinks and hardlinks remain allowed; this is not workspace confinement
or protection against parent mutation, device-open effects, or concurrent writes.
Path projections retain the authored path rather than resolving the opened file.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from stat import S_IMODE, S_ISREG

from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'Filesystem file',
  'goal': "You need one file's content and metadata inside workflow logic, guards, or later adapters.",
  'summary': 'Observe UTF-8 content and metadata from one regular file without publishing its content by default.',
 'sections': [{'heading': 'Use when',
               'items': ["You need one file's content and metadata inside workflow logic, guards, or later adapters.",
                           '`path`: required; supply the regular-file path explicitly. The result preserves the path text you supplied rather '
                          'than replacing it with a resolved filesystem location. Publish basename, size, or '
                          'line_count rather than full content by default; later workflow steps and adapters can use '
                          'the returned content.',
                           'The final path entry must identify a regular file with readable UTF-8 content. If that final entry is a symlink, the probe rejects it instead of reading its target. Missing, unreadable, non-file, and unsupported-content cases stop the probe without publishing partial content.',
                           'The observation protects the final file entry while it is opened, but it is not an atomic '
                           'snapshot of a path that may change concurrently. Symlinks in parent directories may still be traversed.']},
               {'heading': 'What to provide',
                'items': ['`path`: required; provide one non-empty path to a readable UTF-8 regular file.']},
               {'heading': 'Result and boundary',
                'items': ['Later steps can use `path`, `basename`, `filename_without_extension`, `extension`, `exists`, `kind`, `content`, `size`, `owner`, `group`, `permissions`, `modified_at`, and `line_count` from the same opened file.',
                           'Missing, unreadable, non-file, or non-UTF-8 targets fail without partial content. A final symlink is rejected, while a symlink in a parent directory may be traversed. This is not an atomic snapshot: the path can change concurrently, and hardlinks may still refer to the same file.']},
               {'heading': 'Do not use for',
               'items': ['Directory inspection or generic filesystem traversal; this probe requires one regular file '
                         'path.',
                         'Binary or non-UTF-8 content when canonical text content cannot be produced reliably.',
                           'Atomic snapshots, workspace confinement, or general filesystem security isolation. The final '
                           'entry cannot be a symlink, but parent-directory symlinks and hardlinks remain allowed.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
                'references': [{'handle': 'connector.fs', 'summary': 'Parent filesystem connector family'},
                               {'handle': 'operations',
                                'summary': 'Catalog of published operations to check for a narrower supported surface'},
                               {'handle': 'workflow.local_expression.adapter.key_value',
                               'summary': 'One downstream adapter family that can project structured values from '
                                          'fs.file content'}]},
              {'heading': 'Examples', 'items': ['fs.file with inputs {"path": "/workspace/app.env"}']},
              {'heading': 'Inspect next',
                'items': ['workflow.local_expression.adapter.key_value', 'operations']}]})

def info():
    return probe(
        name="file",
        human=HUMAN,
        summary="Read canonical content and metadata from the same opened regular file, without atomic snapshot guarantees.",
        inputs={"path": "string"},
        outputs={
            "path": "string",
            "basename": "string",
            "filename_without_extension": "string",
            "extension": "string",
            "exists": "boolean",
            "kind": "string",
            "content": "string",
            "size": "integer",
            "owner": "string",
            "group": "string",
            "permissions": "string",
            "modified_at": "string",
            "line_count": "integer",
        },
        failure_modes=("path_not_found", "not_a_file", "content_unavailable", "probe_failed"),
        examples=(
            {
                "reference": "fs.file",
                "inputs": {"path": "/workspace/app.env"},
            },
        ),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    raw_path = ctx.input("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Filesystem file probe requires a non-empty path",
            diagnostic_code="probe.fs_file.path_invalid",
            reference=ctx.reference,
            details={"path": raw_path},
        )
    path = Path(raw_path)
    try:
        stat_result = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return fail_with_diagnostic(
            code="path_not_found",
            summary="Filesystem path was not found",
            diagnostic_code="probe.fs_file.path_not_found",
            reference=ctx.reference,
            details={"path": str(path)},
        )
    except OSError as exc:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Filesystem file probe could not inspect the path",
            diagnostic_code="probe.fs_file.stat_failed",
            reference=ctx.reference,
            details={"path": str(path), "reason": str(exc)},
        )

    if not S_ISREG(stat_result.st_mode):
        return fail_with_diagnostic(
            code="not_a_file",
            summary="Filesystem path is not a regular file",
            diagnostic_code="probe.fs_file.not_a_file",
            reference=ctx.reference,
            details={"path": str(path), "kind": _kind_from_mode(stat_result.st_mode)},
        )

    required_flags = ("O_NOFOLLOW", "O_NONBLOCK")
    unavailable_flags = [
        name for name in required_flags
        if type(getattr(os, name, None)) is not int or getattr(os, name) == 0
    ]
    if unavailable_flags:
        return fail_with_diagnostic(
            code="content_unavailable",
            summary="Filesystem file probe requires unavailable safe-open flags",
            diagnostic_code="probe.fs_file.secure_open_unavailable",
            reference=ctx.reference,
            details={"path": str(path), "flags": unavailable_flags, "platform": sys.platform},
        )

    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            try:
                stat_result = os.fstat(fd)
            except OSError as exc:
                return fail_with_diagnostic(
                    code="probe_failed",
                    summary="Filesystem file probe could not inspect the path",
                    diagnostic_code="probe.fs_file.stat_failed",
                    reference=ctx.reference,
                    details={"path": str(path), "reason": str(exc)},
                )
            if not S_ISREG(stat_result.st_mode):
                return fail_with_diagnostic(
                    code="not_a_file",
                    summary="Filesystem path is not a regular file",
                    diagnostic_code="probe.fs_file.not_a_file",
                    reference=ctx.reference,
                    details={"path": str(path), "kind": _kind_from_mode(stat_result.st_mode)},
                )
            # Keep descriptor ownership here even when stream construction fails.
            with os.fdopen(fd, encoding="utf-8", closefd=False) as stream:
                content = stream.read()
        finally:
            os.close(fd)
    except (UnicodeDecodeError, OSError) as exc:
        return fail_with_diagnostic(
            code="content_unavailable",
            summary="Filesystem file probe could not produce file content",
            diagnostic_code="probe.fs_file.content_unavailable",
            reference=ctx.reference,
            details={"path": str(path), "reason": str(exc)},
        )

    filename_without_extension, extension = _split_basename(path.name)

    return ok(
        summary="Filesystem file content and metadata read from the same opened file",
        outputs={
            "path": str(path),
            "basename": path.name,
            "filename_without_extension": filename_without_extension,
            "extension": extension,
            "exists": True,
            "kind": "file",
            "content": content,
            "size": stat_result.st_size,
            "owner": _owner_name(stat_result.st_uid),
            "group": _group_name(stat_result.st_gid),
            "permissions": f"{S_IMODE(stat_result.st_mode):04o}",
            "modified_at": datetime.fromtimestamp(stat_result.st_mtime, tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "line_count": len(content.splitlines()),
        },
        raw={"path": str(path), "encoding": "utf-8"},
    )


def _split_basename(basename: str) -> tuple[str, str]:
    if not basename:
        return "", ""
    dot_index = basename.rfind(".")
    if dot_index == -1:
        return basename, ""
    return basename[:dot_index], basename[dot_index + 1 :]


def _kind_from_mode(mode: int) -> str:
    from stat import S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISLNK, S_ISSOCK

    if S_ISDIR(mode):
        return "directory"
    if S_ISLNK(mode):
        return "symlink"
    if S_ISCHR(mode):
        return "char_device"
    if S_ISBLK(mode):
        return "block_device"
    if S_ISFIFO(mode):
        return "fifo"
    if S_ISSOCK(mode):
        return "socket"
    if S_ISREG(mode):
        return "file"
    return "other"


def _owner_name(uid: int) -> str:
    try:
        import pwd

        return pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        return str(uid)


def _group_name(gid: int) -> str:
    try:
        import grp

        return grp.getgrgid(gid).gr_name
    except (ImportError, KeyError):
        return str(gid)
