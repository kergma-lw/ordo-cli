"""Launcher validation and step wrapping helpers."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.launcher import Launcher
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Step, Workflow

from .resolution import ResolvedOperation
from .value_resolution import ValueResolutionError, resolve_runtime_value


@dataclass(frozen=True, slots=True)
class AppliedLauncher:
    name: str
    definition: Launcher


def validate_step_launchers(workflow: Workflow, profile_name: str | None, launchers: dict[str, Launcher]) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for step in workflow.steps:
        if step.launcher is None:
            continue
        launcher = launchers.get(step.launcher)
        if launcher is None:
            diagnostics.append(
                Diagnostic(
                    code="validation.workflow.step.launcher.unknown",
                    level="error",
                    message=f"Step launcher '{step.launcher}' is not defined by the active profile",
                    path=("steps", step.name, "launcher"),
                    details={"step": step.name, "launcher": step.launcher, "profile": profile_name},
                )
            )
            continue
        if step.operation is None:
            diagnostics.append(
                Diagnostic(
                    code="validation.workflow.step.launcher.form",
                    level="error",
                    message="Launchers are supported only for operation-call steps",
                    path=("steps", step.name, "launcher"),
                    details={"step": step.name, "launcher": step.launcher},
                )
            )
            continue
        target = step.operation.uses
        if launcher.connector is not None and launcher.connector != target:
            diagnostics.append(
                Diagnostic(
                    code="validation.workflow.step.launcher.connector_mismatch",
                    level="error",
                    message="Step launcher connector does not match the step operation",
                    path=("steps", step.name, "launcher"),
                    details={"step": step.name, "launcher": step.launcher, "launcher_connector": launcher.connector, "step_connector": target},
                )
            )
            continue
        if launcher.connector is None and target != "shell.command":
            diagnostics.append(
                Diagnostic(
                    code="validation.workflow.step.launcher.unsupported_target",
                    level="error",
                    message="Launcher without an explicit connector may wrap only shell.command in the MVP",
                    path=("steps", step.name, "launcher"),
                    details={"step": step.name, "launcher": step.launcher, "step_connector": target},
                )
            )
    return tuple(diagnostics)


def apply_launcher_to_step(step: Step, resolved_step: ResolvedOperation, workflow: Workflow, launchers: dict[str, Launcher]) -> tuple[ResolvedOperation | None, AppliedLauncher | None, OperationResult | None]:
    if step.launcher is None:
        return resolved_step, None, None
    launcher = launchers.get(step.launcher)
    if launcher is None:
        return None, None, OperationResult(
            status="execution_error",
            summary="Selected launcher is not defined by the active profile",
            diagnostics=(
                Diagnostic(
                    code="runtime.step.launcher.unknown",
                    level="error",
                    message="Selected launcher is not defined by the active profile",
                    path=("steps", step.name, "launcher"),
                    details={"step": step.name, "launcher": step.launcher},
                ),
            ),
        )
    if resolved_step.reference != "shell.command":
        return None, None, OperationResult(
            status="execution_error",
            summary="Selected launcher cannot wrap this operation in the MVP",
            diagnostics=(
                Diagnostic(
                    code="runtime.step.launcher.unsupported_target",
                    level="error",
                    message="Selected launcher cannot wrap this operation in the MVP",
                    path=("steps", step.name, "launcher"),
                    details={"step": step.name, "launcher": step.launcher, "reference": resolved_step.reference},
                ),
            ),
        )

    try:
        original_command = resolve_runtime_value(step.operation.with_.get("command"), workflow)
    except ValueResolutionError as exc:
        return None, None, OperationResult(
            status="execution_error",
            summary=exc.message,
            diagnostics=(exc.to_diagnostic(),),
        )
    if not isinstance(original_command, str):
        return None, None, OperationResult(
            status="execution_error",
            summary="Launcher-wrapped shell command must resolve to a string",
            diagnostics=(
                Diagnostic(
                    code="runtime.step.launcher.command_type",
                    level="error",
                    message="Launcher-wrapped shell command must resolve to a string",
                    path=("steps", step.name, "launcher"),
                    details={"actual_type": type(original_command).__name__},
                ),
            ),
        )

    wrapped = _wrap_shell_command(original_command, launcher)
    declared_with = dict(resolved_step.declared_with or {})
    declared_with["command"] = wrapped
    return (
        ResolvedOperation(
            reference=resolved_step.reference,
            connector_namespace=resolved_step.connector_namespace,
            operation=resolved_step.operation,
            source=resolved_step.source,
            declared_with=declared_with,
        ),
        AppliedLauncher(name=step.launcher, definition=launcher),
        None,
    )


def _wrap_shell_command(command: str, launcher: Launcher) -> str:
    before = launcher.before or "true"
    after = launcher.after or "true"
    return (
        "set +e; "
        f"{{ {before}; }}; __ordo_before_status=$?; "
        "if [ $__ordo_before_status -ne 0 ]; then exit $__ordo_before_status; fi; "
        f"{{ {command}; }}; __ordo_main_status=$?; "
        f"{{ {after}; }}; __ordo_after_status=$?; "
        "if [ $__ordo_main_status -ne 0 ]; then exit $__ordo_main_status; fi; "
        "if [ $__ordo_after_status -ne 0 ]; then exit $__ordo_after_status; fi; "
        "exit 0"
    )
