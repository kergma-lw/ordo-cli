"""Runtime helpers for project-local routine resolution and execution."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow
from ordo.routines import RoutineEntry, RoutineRegistry, build_routine_operation_contract, load_workflow_routine_registry

from .value_resolution import ValueResolutionError, resolve_runtime_value

_LOG_TAIL_LINE_COUNT = 20


def resolve_routine_entry(*, workflow: Workflow, routine_id: str) -> tuple[RoutineRegistry, RoutineEntry] | Diagnostic:
    """Resolve one routine id through the workflow-associated routine registry."""

    try:
        registry = load_workflow_routine_registry(workflow)
    except Exception as exc:
        if hasattr(exc, "diagnostics"):
            return getattr(exc, "diagnostics")[0]
        raise
    entry = registry.routines.get(routine_id)
    if entry is None:
        return Diagnostic(
            code="resolution.unknown_routine",
            level="error",
            message=f"Unknown routine identifier '{routine_id}'",
            path=(),
            details={"routine_id": routine_id, "registry": str(registry.path)},
        )
    return registry, entry


def routine_operation_contract(entry: RoutineEntry):
    """Return the temporary operation contract used for routine resolution."""

    return build_routine_operation_contract(entry, use_declared_kind=True)


def execute_routine_step(resolved_step, workflow: Workflow) -> OperationResult:
    """Execute one resolved routine step with bounded log output."""

    routine_id = resolved_step.declared_with.get("id") if isinstance(resolved_step.declared_with, dict) else None
    if not isinstance(routine_id, str) or not routine_id:
        return OperationResult(status="execution_error", summary="Routine step is missing a resolved routine identifier")
    resolved = resolve_routine_entry(workflow=workflow, routine_id=routine_id)
    if isinstance(resolved, Diagnostic):
        return OperationResult(status="execution_error", summary=resolved.message, diagnostics=(resolved,))
    registry, entry = resolved
    try:
        argv = _materialize_routine_argv(entry, resolved_step.declared_with or {}, workflow)
    except ValueResolutionError as exc:
        return OperationResult(status="execution_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))
    stdout_path, stderr_path = _routine_log_paths(routine_id)
    try:
        completed = _run_with_log_capture(argv, stdout_path=stdout_path, stderr_path=stderr_path)
    except OSError as exc:
        diagnostic = Diagnostic(
            code="runtime.routine.start_failed",
            level="error",
            message="Routine could not be started",
            details={"routine_id": routine_id, "registry": str(registry.path), "argv": argv, "os_error": str(exc)},
        )
        return OperationResult(
            status="execution_error",
            summary=f"Routine '{routine_id}' could not be started",
            diagnostics=(diagnostic,),
            raw={"stdout_path": str(stdout_path), "stderr_path": str(stderr_path)},
        )
    stdout_tail = _read_log_tail(stdout_path)
    stderr_tail = _read_log_tail(stderr_path)
    output_mode = entry.outputs.get("mode") if isinstance(entry.outputs, dict) else None
    if entry.kind == "probe" and output_mode == "data" and completed.returncode == 0:
        return _probe_data_result(
            routine_id=routine_id,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
        )
    outputs = {
        "routine_id": routine_id,
        "exit_code": completed.returncode,
        "log_path": str(stdout_path),
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }
    raw = {"stdout_path": str(stdout_path), "stderr_path": str(stderr_path)}
    if completed.returncode == 0:
        summary = f"Routine '{routine_id}' completed successfully"
        if entry.kind == "probe":
            summary = f"Routine probe '{routine_id}' completed successfully"
        return OperationResult(status="ok", summary=summary, outputs=outputs, raw=raw)
    return OperationResult(status="routine_failed", summary=f"Routine '{routine_id}' failed", outputs=outputs, raw=raw)


def _probe_data_result(
    *,
    routine_id: str,
    stdout_path: Path,
    stderr_path: Path,
    stdout_tail: str,
    stderr_tail: str,
) -> OperationResult:
    try:
        payload = json.loads(stdout_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        diagnostic = Diagnostic(
            code="runtime.routine.probe_output_invalid",
            level="error",
            message="Routine probe did not produce valid JSON output",
            details={"routine_id": routine_id, "error": str(exc), "stdout_path": str(stdout_path)},
        )
        return OperationResult(
            status="execution_error",
            summary=f"Routine probe '{routine_id}' returned invalid structured output",
            diagnostics=(diagnostic,),
            outputs={"routine_id": routine_id, "log_path": str(stdout_path), "stdout_tail": stdout_tail, "stderr_tail": stderr_tail},
            raw={"stdout_path": str(stdout_path), "stderr_path": str(stderr_path)},
        )
    return OperationResult(
        status="ok",
        summary=f"Routine probe '{routine_id}' returned structured data",
        outputs={"routine_id": routine_id, "log_path": str(stdout_path), "data": payload},
        raw={"stdout_path": str(stdout_path), "stderr_path": str(stderr_path)},
    )


def _materialize_routine_argv(entry: RoutineEntry, declared_with: dict[str, object], workflow: Workflow) -> list[str]:
    args_payload = declared_with.get("args", {})
    if not isinstance(args_payload, dict):
        args_payload = {}
    resolved_args: dict[str, object] = {}
    for arg_name, value in args_payload.items():
        resolved_args[arg_name] = resolve_runtime_value(value, workflow)
    argv: list[str] = []
    for item in entry.implementation.argv:
        if item.startswith("{") and item.endswith("}") and item.count("{") == 1 and item.count("}") == 1:
            arg_name = item[1:-1]
            resolved_value = resolved_args.get(arg_name)
            if resolved_value is None:
                argv.append("")
            elif isinstance(resolved_value, list):
                argv.extend(str(part) for part in resolved_value)
            else:
                argv.append(str(resolved_value))
            continue
        argv.append(item)
    return [part for part in argv if part != ""]


def _run_with_log_capture(argv: list[str], *, stdout_path: Path, stderr_path: Path) -> subprocess.CompletedProcess[str]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
        return subprocess.run(argv, check=False, text=True, stdout=stdout_handle, stderr=stderr_handle)


def _routine_log_paths(routine_id: str) -> tuple[Path, Path]:
    prefix = routine_id.replace("/", "_").replace(".", "-")
    log_dir = Path(tempfile.gettempdir()) / "ordo"
    stdout_handle = tempfile.NamedTemporaryFile(prefix=f"{prefix}-", suffix=".stdout.log", dir=log_dir if log_dir.exists() else None, delete=False)
    stderr_handle = tempfile.NamedTemporaryFile(prefix=f"{prefix}-", suffix=".stderr.log", dir=log_dir if log_dir.exists() else None, delete=False)
    stdout_path = Path(stdout_handle.name)
    stderr_path = Path(stderr_handle.name)
    stdout_handle.close()
    stderr_handle.close()
    return stdout_path, stderr_path


def _read_log_tail(path: Path) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-_LOG_TAIL_LINE_COUNT:])
