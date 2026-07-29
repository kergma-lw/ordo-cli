"""fs.file probe."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from stat import S_IMODE, S_ISREG

from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe


def info():
    return probe(
        name="file",
        summary="Observe one filesystem path as one file snapshot with canonical content and file metadata.",
        inputs={"path": "string"},
        outputs={
            "path": "string",
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

    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return fail_with_diagnostic(
            code="content_unavailable",
            summary="Filesystem file probe could not produce file content",
            diagnostic_code="probe.fs_file.content_unavailable",
            reference=ctx.reference,
            details={"path": str(path), "reason": str(exc)},
        )

    return ok(
        summary="Filesystem file snapshot read successfully",
        outputs={
            "path": str(path),
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
