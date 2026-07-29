"""fs.text probe."""

from __future__ import annotations

from pathlib import Path

from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe


def info():
    return probe(
        name="text",
        inputs={"path": "string"},
        outputs={
            "path": "string",
            "text": "string",
            "line_count": "integer",
        },
        failure_modes=("path_not_found", "not_a_file", "not_text", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    raw_path = ctx.input("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Filesystem text probe requires a non-empty path",
            diagnostic_code="probe.fs_text.path_invalid",
            reference=ctx.reference,
            details={"path": raw_path},
        )
    path = Path(raw_path)
    if not path.exists():
        return fail_with_diagnostic(
            code="path_not_found",
            summary="Filesystem path was not found",
            diagnostic_code="probe.fs_text.path_not_found",
            reference=ctx.reference,
            details={"path": str(path)},
        )
    if not path.is_file():
        return fail_with_diagnostic(
            code="not_a_file",
            summary="Filesystem path is not a regular file",
            diagnostic_code="probe.fs_text.not_a_file",
            reference=ctx.reference,
            details={"path": str(path)},
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return fail_with_diagnostic(
            code="not_text",
            summary="Filesystem file could not be decoded as UTF-8 text",
            diagnostic_code="probe.fs_text.not_text",
            reference=ctx.reference,
            details={"path": str(path), "encoding": "utf-8", "reason": str(exc)},
        )
    except OSError as exc:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Filesystem text probe could not read the file",
            diagnostic_code="probe.fs_text.read_failed",
            reference=ctx.reference,
            details={"path": str(path), "reason": str(exc)},
        )
    return ok(
        summary="Filesystem text snapshot read successfully",
        outputs={
            "path": str(path),
            "text": text,
            "line_count": len(text.splitlines()),
        },
        raw={"path": str(path), "encoding": "utf-8"},
    )
