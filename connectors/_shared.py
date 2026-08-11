"""Shared connector runtime helpers."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import TYPE_CHECKING

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow
from ordo.runtime.local_expression_engine.core import ListNode, LiteralNode, ObjectEntryNode, ObjectNode, ReferenceNode, StateReferenceNode, ValueExpressionNode as GuardExpressionNode
from ordo.runtime.state import RuntimeStateError, read_state_document, read_state_value, resolve_state_target
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value

if TYPE_CHECKING:
    from ordo.runtime.resolution import ResolvedExpressionProbe, ResolvedOperation


def require_input(workflow: Workflow, resolved: "ResolvedOperation | ResolvedExpressionProbe", key: str) -> JSONValue | OperationResult:
    value = resolved.operation.inputs.get(key)
    _ = value
    resolved_inputs = getattr(resolved, "resolved_inputs", None)
    if isinstance(resolved_inputs, dict) and key in resolved_inputs:
        return resolved_inputs[key]
    candidate_inputs = getattr(resolved, "declared_with", None)
    if isinstance(candidate_inputs, dict) and key in candidate_inputs:
        candidate = candidate_inputs[key]
        if candidate is not None:
            try:
                return resolve_runtime_value(candidate, workflow)
            except ValueResolutionError as exc:
                return OperationResult(
                    status="input_error",
                    summary=exc.message,
                    diagnostics=(exc.to_diagnostic(),),
                )
    for guard in workflow.guards:
        if guard.operation is not None and guard.operation.uses == resolved.reference and key in guard.operation.with_:
            candidate = guard.operation.with_[key]
            if candidate is not None:
                try:
                    return resolve_runtime_value(candidate, workflow)
                except ValueResolutionError as exc:
                    return OperationResult(
                        status="input_error",
                        summary=exc.message,
                        diagnostics=(exc.to_diagnostic(),),
                    )
    for step in workflow.steps:
        if step.operation is not None and step.operation.uses == resolved.reference and key in step.operation.with_:
            candidate = step.operation.with_[key]
            if candidate is not None:
                try:
                    return resolve_runtime_value(candidate, workflow)
                except ValueResolutionError as exc:
                    return OperationResult(
                        status="input_error",
                        summary=exc.message,
                        diagnostics=(exc.to_diagnostic(),),
                    )
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


def require_expression_input(workflow: Workflow, resolved: "ResolvedExpressionProbe", key: str) -> JSONValue | OperationResult:
    for argument_name, argument_value in resolved.arguments:
        if argument_name == key:
            value = evaluate_argument_value(argument_value, workflow)
            if value is _MISSING:
                return _missing_input_result(resolved.reference, key)
            return value
    return _missing_input_result(resolved.reference, key)


def evaluate_argument_value(node: GuardExpressionNode, workflow: Workflow) -> JSONValue | object:
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, ReferenceNode):
        if not node.parts or node.parts[0] != "inputs":
            return _MISSING
        current: JSONValue = workflow.inputs
        for part in node.parts[1:]:
            if not isinstance(current, dict) or part not in current:
                return _MISSING
            current = current[part]
        return current
    if isinstance(node, StateReferenceNode):
        try:
            expression = _state_expression_text(node)
            target = resolve_state_target(expression, workflow)
            document = read_state_document(target.location)
            value = read_state_value(document, key=target.key, fields=target.fields)
        except RuntimeStateError:
            return _MISSING
        return _MISSING if value is None else value
    if isinstance(node, ListNode):
        values: list[JSONValue] = []
        for item in node.items:
            value = evaluate_argument_value(item, workflow)
            if value is _MISSING:
                return _MISSING
            values.append(value)  # type: ignore[arg-type]
        return values
    if isinstance(node, ObjectEntryNode):
        return evaluate_argument_value(node.value, workflow)
    if isinstance(node, ObjectNode):
        values: dict[str, JSONValue] = {}
        for entry in node.entries:
            value = evaluate_argument_value(entry.value, workflow)
            if value is _MISSING:
                return _MISSING
            values[entry.key] = value  # type: ignore[assignment]
        return values
    return _MISSING


def _state_expression_text(node: StateReferenceNode) -> str:
    key_ref = ".".join(node.key_reference)
    suffix = "" if not node.fields else "." + ".".join(node.fields)
    return f"state.{node.state_role}[{key_ref}]{suffix}"


def run_command(command: Sequence[str], *, reference: str) -> OperationResult:
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
        outputs={"returncode": completed.returncode},
        diagnostics=diagnostics,
        raw={"stdout": completed.stdout, "stderr": completed.stderr},
    )


def not_implemented(reference: str, *, kind: str) -> OperationResult:
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


_MISSING = object()


def _missing_input_result(reference: str, key: str) -> OperationResult:
    return OperationResult(
        status="input_error",
        summary=f"Required input '{key}' is missing",
        diagnostics=(
            Diagnostic(
                code="operation.input_missing",
                level="error",
                message=f"Required input '{key}' is missing",
                path=(),
                details={"reference": reference, "input": key},
            ),
        ),
    )
