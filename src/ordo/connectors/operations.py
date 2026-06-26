"""Initial canonical connector operation implementations."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from typing import TYPE_CHECKING

from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow

if TYPE_CHECKING:
    from ordo.runtime.resolution import ResolvedOperation


def execute_action(resolved_step: ResolvedOperation, workflow: Workflow) -> OperationResult:
    """Execute a supported action operation with structured results."""

    reference = resolved_step.reference
    if reference == "shell.command":
        command = _require_input(workflow, resolved_step, "command")
        if isinstance(command, OperationResult):
            return command
        return _run_command(["bash", "-lc", command], reference=reference)

    return _not_implemented(reference, kind="action")


def evaluate_probe(resolved_guard: ResolvedOperation, workflow: Workflow) -> OperationResult:
    """Evaluate a supported probe operation with structured observations."""

    reference = resolved_guard.reference
    if reference == "git.clean_worktree":
        return _git_clean_worktree(reference)
    if reference == "git.branch_not_main":
        return _git_branch_not_main(reference)
    if reference == "gh.issue.view":
        issue = _require_input(workflow, resolved_guard, "issue")
        if isinstance(issue, OperationResult):
            return issue
        return _gh_issue_view(reference, issue)

    return _not_implemented(reference, kind="probe")


def _git_clean_worktree(reference: str) -> OperationResult:
    result = _run_command(["git", "status", "--porcelain"], reference=reference)
    if result.status != "ok":
        return result

    stdout = str(result.raw.get("stdout", ""))
    dirty_paths = [line[3:] for line in stdout.splitlines() if len(line) >= 4]
    return OperationResult(
        status="ok",
        summary="Git worktree inspected successfully",
        observations={"clean": not dirty_paths, "dirty_paths": dirty_paths},
        raw=result.raw,
    )


def _git_branch_not_main(reference: str) -> OperationResult:
    result = _run_command(["git", "branch", "--show-current"], reference=reference)
    if result.status != "ok":
        return result

    branch = str(result.raw.get("stdout", "")).strip()
    return OperationResult(
        status="ok" if branch != "main" else "guard_failed",
        summary="Current branch inspected successfully",
        observations={"allowed": branch != "main", "current_branch": branch},
        raw=result.raw,
        diagnostics=() if branch != "main" else (
            Diagnostic(
                code="guard.branch_main",
                level="error",
                message="Current branch is main",
                path=(),
                details={"reference": reference, "current_branch": branch},
            ),
        ),
    )


def _gh_issue_view(reference: str, issue: str) -> OperationResult:
    result = _run_command(
        ["gh", "issue", "view", issue, "--json", "number,title,state,body,url"],
        reference=reference,
    )
    if result.status != "ok":
        return result

    stdout = str(result.raw.get("stdout", ""))
    try:
        issue_data = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as exc:
        return OperationResult(
            status="probe_failed",
            summary="GitHub issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_issue_view.invalid_json",
                    level="error",
                    message="GitHub issue output was not valid JSON",
                    path=(),
                    details={"reference": reference, "error": str(exc)},
                ),
            ),
            raw=result.raw,
        )

    return OperationResult(
        status="ok",
        summary="GitHub issue retrieved successfully",
        observations={"issue": issue_data},
        raw=result.raw,
    )


def _require_input(workflow: Workflow, resolved: ResolvedOperation, key: str) -> str | OperationResult:
    value = resolved.operation.inputs.get(key)
    _ = value
    for guard in workflow.guards:
        if guard.operation.uses == resolved.reference and key in guard.operation.with_:
            candidate = guard.operation.with_[key]
            if isinstance(candidate, str):
                return candidate
    for step in workflow.steps:
        if step.operation.uses == resolved.reference and key in step.operation.with_:
            candidate = step.operation.with_[key]
            if isinstance(candidate, str):
                return candidate
    return OperationResult(
        status="input_error",
        summary=f"Required input '{key}' is missing",
        diagnostics=(
            Diagnostic(
                code="operation.input_missing",
                level="error",
                message=f"Required input '{key}' is missing",
                path=(),
                details={"reference": resolved.reference, "input": key},
            ),
        ),
    )


def _run_command(command: Sequence[str], *, reference: str) -> OperationResult:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return OperationResult(
            status="execution_error",
            summary="Command execution failed before completion",
            diagnostics=(
                Diagnostic(
                    code="operation.command_os_error",
                    level="error",
                    message="Command execution failed before completion",
                    path=(),
                    details={"reference": reference, "error": str(exc)},
                ),
            ),
            raw={"stdout": "", "stderr": str(exc)},
        )

    status = "ok" if completed.returncode == 0 else "execution_error"
    diagnostics = ()
    if completed.returncode != 0:
        diagnostics = (
            Diagnostic(
                code="operation.command_failed",
                level="error",
                message="Command returned non-zero exit status",
                path=(),
                details={"reference": reference, "returncode": completed.returncode},
            ),
        )

    return OperationResult(
        status=status,
        summary="Command completed successfully" if completed.returncode == 0 else "Command returned non-zero exit status",
        observations={"returncode": completed.returncode},
        diagnostics=diagnostics,
        raw={"stdout": completed.stdout, "stderr": completed.stderr},
    )


def _not_implemented(reference: str, *, kind: str) -> OperationResult:
    return OperationResult(
        status=f"{kind}_not_implemented",
        summary=f"Operation '{reference}' does not have a concrete implementation yet",
        diagnostics=(
            Diagnostic(
                code="operation.not_implemented",
                level="error",
                message=f"Operation '{reference}' does not have a concrete implementation yet",
                path=(),
                details={"reference": reference, "kind": kind},
            ),
        ),
    )
