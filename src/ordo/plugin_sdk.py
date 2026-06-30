"""Minimal connector plugin SDK for the first implementation spike."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from ordo.model.diagnostic import Diagnostic as RuntimeDiagnostic
from ordo.model.json import JSONObject, JSONValue
from ordo.model.runtime import OperationResult

if TYPE_CHECKING:
    from ordo.runtime.resolution import ResolvedExpressionProbe, ResolvedOperation
    from ordo.model.workflow import Workflow


OperationKind = Literal["probe", "action"]
DiagnosticLevel = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    level: DiagnosticLevel
    message: str
    details: JSONObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OperationOutcome:
    status: str
    summary: str | None = None
    outputs: JSONObject = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
    raw: JSONObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PublishedOperation:
    name: str
    kind: OperationKind
    handler: Callable[["OperationContext"], OperationOutcome]
    inputs: JSONObject = field(default_factory=dict)
    prerequisites: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    outputs: JSONObject = field(default_factory=dict)
    failure_modes: tuple[str, ...] = ()
    deprecated: bool = False
    replaced_by: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PublishedBootstrap:
    prerequisites: tuple[str, ...]
    context_fields: tuple[str, ...]
    values: JSONObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int
    raw: JSONObject


class MappedOutcomeError(Exception):
    """Internal control-flow exception for mapped local failures."""

    def __init__(self, outcome: OperationOutcome) -> None:
        super().__init__(outcome.summary or outcome.status)
        self.outcome = outcome


class OperationContext:
    """Minimal authoring context for plugin-sdk operations."""

    def __init__(
        self,
        *,
        resolved: "ResolvedOperation | ResolvedExpressionProbe",
        workflow: "Workflow",
        bootstrap: PublishedBootstrap,
        caller: Callable[[str, JSONObject | None], OperationOutcome],
    ) -> None:
        self._resolved = resolved
        self._workflow = workflow
        self._bootstrap = bootstrap
        self._caller = caller

    def input(self, name: str) -> JSONValue:
        from connectors._shared import require_expression_input, require_input

        if hasattr(self._resolved, "arguments"):
            value = require_expression_input(self._workflow, self._resolved, name)  # type: ignore[arg-type]
        else:
            value = require_input(self._workflow, self._resolved, name)

        if isinstance(value, OperationResult):
            raise MappedOutcomeError(_outcome_from_runtime_result(value))
        return value

    def bootstrap(self) -> PublishedBootstrap:
        return self._bootstrap

    @property
    def reference(self) -> str:
        return self._resolved.reference

    def call(self, name: str, *, inputs: JSONObject | None = None) -> OperationOutcome:
        return self._caller(name, inputs)

    def command(self, argv: Sequence[str], *, failures: Mapping[str, str] | None = None) -> CommandResult:
        try:
            completed = subprocess.run(list(argv), capture_output=True, text=True, check=False)
        except OSError as exc:
            code = None if failures is None else failures.get("os_error")
            if code is None:
                code = "execution_error"
            raise MappedOutcomeError(
                OperationOutcome(
                    status=code,
                    summary="Command execution failed before completion",
                    diagnostics=(
                        Diagnostic(
                            code="operation.command_os_error",
                            level="error",
                            message="Command execution failed before completion",
                            details={"reference": self._resolved.reference, "error": str(exc)},
                        ),
                    ),
                    raw={"argv": list(argv), "stdout": "", "stderr": str(exc), "os_error": str(exc)},
                )
            ) from exc

        if completed.returncode != 0:
            code = None if failures is None else failures.get("nonzero")
            if code is None:
                code = "execution_error"
            raise MappedOutcomeError(
                OperationOutcome(
                    status=code,
                    summary="Command returned non-zero exit status",
                    diagnostics=(
                        Diagnostic(
                            code="operation.command_failed",
                            level="error",
                            message="Command returned non-zero exit status",
                            details={"reference": self._resolved.reference, "returncode": completed.returncode},
                        ),
                    ),
                    raw={
                        "argv": list(argv),
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                        "returncode": completed.returncode,
                    },
                )
            )

        return CommandResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            raw={
                "argv": list(argv),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
            },
        )


def probe(
    *,
    name: str,
    handler: Callable[[OperationContext], OperationOutcome],
    inputs: JSONObject | None = None,
    prerequisites: tuple[str, ...] = (),
    outputs: JSONObject | None = None,
    failure_modes: tuple[str, ...] = (),
    deprecated: bool = False,
    replaced_by: tuple[str, ...] = (),
) -> PublishedOperation:
    return PublishedOperation(
        name=name,
        kind="probe",
        handler=handler,
        inputs={} if inputs is None else dict(inputs),
        prerequisites=prerequisites,
        outputs={} if outputs is None else dict(outputs),
        failure_modes=failure_modes,
        deprecated=deprecated,
        replaced_by=replaced_by,
    )


def action(
    *,
    name: str,
    handler: Callable[[OperationContext], OperationOutcome],
    inputs: JSONObject | None = None,
    prerequisites: tuple[str, ...] = (),
    effects: tuple[str, ...] = (),
    outputs: JSONObject | None = None,
    failure_modes: tuple[str, ...] = (),
    deprecated: bool = False,
    replaced_by: tuple[str, ...] = (),
) -> PublishedOperation:
    return PublishedOperation(
        name=name,
        kind="action",
        handler=handler,
        inputs={} if inputs is None else dict(inputs),
        prerequisites=prerequisites,
        effects=effects,
        outputs={} if outputs is None else dict(outputs),
        failure_modes=failure_modes,
        deprecated=deprecated,
        replaced_by=replaced_by,
    )


def ok(*, summary: str | None = None, outputs: JSONObject | None = None, raw: JSONObject | None = None) -> OperationOutcome:
    return OperationOutcome(
        status="ok",
        summary=summary,
        outputs={} if outputs is None else dict(outputs),
        raw={} if raw is None else dict(raw),
    )


def fail(
    *,
    code: str,
    summary: str | None = None,
    outputs: JSONObject | None = None,
    diagnostics: tuple[Diagnostic, ...] = (),
    raw: JSONObject | None = None,
) -> OperationOutcome:
    return OperationOutcome(
        status=code,
        summary=summary,
        outputs={} if outputs is None else dict(outputs),
        diagnostics=diagnostics,
        raw={} if raw is None else dict(raw),
    )


def not_implemented(*, reference: str, kind: str) -> OperationOutcome:
    return OperationOutcome(
        status=f"{kind}_not_implemented",
        summary=f"Operation '{reference}' does not have a concrete implementation yet",
        diagnostics=(
            Diagnostic(
                code="operation.not_implemented",
                level="error",
                message=f"Operation '{reference}' does not have a concrete implementation yet",
                details={"reference": reference, "kind": kind},
            ),
        ),
    )


def adapt_outcome(outcome: OperationOutcome) -> OperationResult:
    return OperationResult(
        status=outcome.status,
        summary=outcome.summary,
        observations=dict(outcome.outputs),
        diagnostics=tuple(
            RuntimeDiagnostic(
                code=diagnostic.code,
                level=diagnostic.level,
                message=diagnostic.message,
                details=dict(diagnostic.details),
            )
            for diagnostic in outcome.diagnostics
        ),
        raw=dict(outcome.raw),
    )


def _outcome_from_runtime_result(result: OperationResult) -> OperationOutcome:
    return OperationOutcome(
        status=result.status,
        summary=result.summary,
        outputs=dict(result.observations),
        diagnostics=tuple(
            Diagnostic(
                code=diagnostic.code,
                level=diagnostic.level,
                message=diagnostic.message,
                details=dict(diagnostic.details),
            )
            for diagnostic in result.diagnostics
        ),
        raw=dict(result.raw),
    )
