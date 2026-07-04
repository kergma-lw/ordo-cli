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
class BootstrapOutcome:
    status: str
    summary: str | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    raw: JSONObject = field(default_factory=dict)
    context: JSONObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PublishedOperation:
    name: str
    kind: OperationKind
    handler: Callable[["OperationContext"], OperationOutcome]
    summary: str | None = None
    inputs: JSONObject = field(default_factory=dict)
    prerequisites: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    outputs: JSONObject = field(default_factory=dict)
    failure_modes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    examples: tuple[JSONObject, ...] = ()
    maturity: str = "stable"
    deprecated: bool = False
    replaced_by: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PublishedBootstrap:
    prerequisites: tuple[str, ...]
    context_fields: tuple[str, ...]
    handler: Callable[["BootstrapContext"], BootstrapOutcome] | None = None


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


class MappedBootstrapError(Exception):
    """Internal control-flow exception for mapped bootstrap failures."""

    def __init__(self, outcome: BootstrapOutcome) -> None:
        super().__init__(outcome.summary or outcome.status)
        self.outcome = outcome


class BootstrapContext:
    """Minimal authoring context for executable family bootstrap."""

    def command(self, argv: Sequence[str], *, failures: Mapping[str, str] | None = None) -> CommandResult:
        return _run_command(argv, failures=failures, reference="bootstrap", error_type=MappedBootstrapError)


class OperationContext:
    """Minimal authoring context for plugin-sdk operations."""

    def __init__(
        self,
        *,
        resolved: "ResolvedOperation | ResolvedExpressionProbe",
        workflow: "Workflow",
        bootstrap: BootstrapOutcome,
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

    def bootstrap(self) -> BootstrapOutcome:
        return self._bootstrap

    @property
    def reference(self) -> str:
        return self._resolved.reference

    def call(self, name: str, *, inputs: JSONObject | None = None) -> OperationOutcome:
        return self._caller(name, inputs)

    def command(self, argv: Sequence[str], *, failures: Mapping[str, str] | None = None) -> CommandResult:
        return _run_command(argv, failures=failures, reference=self._resolved.reference, error_type=MappedOutcomeError)


def bootstrap(
    *,
    prerequisites: tuple[str, ...] = (),
    context_fields: tuple[str, ...] = (),
    handler: Callable[[BootstrapContext], BootstrapOutcome] | None = None,
) -> PublishedBootstrap:
    return PublishedBootstrap(
        prerequisites=prerequisites,
        context_fields=context_fields,
        handler=handler,
    )


def probe(
    *,
    name: str,
    handler: Callable[[OperationContext], OperationOutcome],
    summary: str | None = None,
    inputs: JSONObject | None = None,
    prerequisites: tuple[str, ...] = (),
    outputs: JSONObject | None = None,
    failure_modes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    examples: tuple[JSONObject, ...] = (),
    maturity: str = "stable",
    deprecated: bool = False,
    replaced_by: tuple[str, ...] = (),
) -> PublishedOperation:
    return PublishedOperation(
        name=name,
        kind="probe",
        handler=handler,
        summary=summary,
        inputs={} if inputs is None else dict(inputs),
        prerequisites=prerequisites,
        outputs={} if outputs is None else dict(outputs),
        failure_modes=failure_modes,
        tags=tags,
        examples=examples,
        maturity=maturity,
        deprecated=deprecated,
        replaced_by=replaced_by,
    )


def action(
    *,
    name: str,
    handler: Callable[[OperationContext], OperationOutcome],
    summary: str | None = None,
    inputs: JSONObject | None = None,
    prerequisites: tuple[str, ...] = (),
    effects: tuple[str, ...] = (),
    outputs: JSONObject | None = None,
    failure_modes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    examples: tuple[JSONObject, ...] = (),
    maturity: str = "stable",
    deprecated: bool = False,
    replaced_by: tuple[str, ...] = (),
) -> PublishedOperation:
    return PublishedOperation(
        name=name,
        kind="action",
        handler=handler,
        summary=summary,
        inputs={} if inputs is None else dict(inputs),
        prerequisites=prerequisites,
        effects=effects,
        outputs={} if outputs is None else dict(outputs),
        failure_modes=failure_modes,
        tags=tags,
        examples=examples,
        maturity=maturity,
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


def bootstrap_ok(*, summary: str | None = None, context: JSONObject | None = None, raw: JSONObject | None = None) -> BootstrapOutcome:
    return BootstrapOutcome(
        status="ok",
        summary=summary,
        context={} if context is None else dict(context),
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


def fail_with_diagnostic(
    *,
    code: str,
    summary: str,
    diagnostic_code: str,
    message: str | None = None,
    level: DiagnosticLevel = "error",
    reference: str | None = None,
    details: JSONObject | None = None,
    outputs: JSONObject | None = None,
    raw: JSONObject | None = None,
) -> OperationOutcome:
    diagnostic_details = {} if details is None else dict(details)
    if reference is not None and "reference" not in diagnostic_details:
        diagnostic_details["reference"] = reference
    return fail(
        code=code,
        summary=summary,
        outputs=outputs,
        diagnostics=(
            Diagnostic(
                code=diagnostic_code,
                level=level,
                message=summary if message is None else message,
                details=diagnostic_details,
            ),
        ),
        raw=raw,
    )


def bootstrap_fail(
    *,
    code: str,
    summary: str | None = None,
    diagnostics: tuple[Diagnostic, ...] = (),
    raw: JSONObject | None = None,
    context: JSONObject | None = None,
) -> BootstrapOutcome:
    return BootstrapOutcome(
        status=code,
        summary=summary,
        diagnostics=diagnostics,
        raw={} if raw is None else dict(raw),
        context={} if context is None else dict(context),
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
        outputs=dict(outcome.outputs),
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


def adapt_bootstrap(outcome: BootstrapOutcome) -> OperationResult:
    return OperationResult(
        status=outcome.status,
        summary=outcome.summary,
        outputs=dict(outcome.context),
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


def _bootstrap_from_runtime_result(result: OperationResult) -> BootstrapOutcome:
    return BootstrapOutcome(
        status=result.status,
        summary=result.summary,
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
        context=dict(result.outputs),
    )


def _outcome_from_runtime_result(result: OperationResult) -> OperationOutcome:
    return OperationOutcome(
        status=result.status,
        summary=result.summary,
        outputs=dict(result.outputs),
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


def _run_command(
    argv: Sequence[str],
    *,
    failures: Mapping[str, str] | None,
    reference: str,
    error_type: type[MappedOutcomeError] | type[MappedBootstrapError],
) -> CommandResult:
    try:
        completed = subprocess.run(list(argv), capture_output=True, text=True, check=False)
    except OSError as exc:
        code = None if failures is None else failures.get("os_error")
        if code is None:
            code = "execution_error"
        raise error_type(
            _error_outcome(
                outcome_type=error_type,
                status=code,
                summary="Command execution failed before completion",
                diagnostic_code="operation.command_os_error",
                diagnostic_message="Command execution failed before completion",
                details={"reference": reference, "error": str(exc)},
                raw={"argv": list(argv), "stdout": "", "stderr": str(exc), "os_error": str(exc)},
            )
        ) from exc

    if completed.returncode != 0:
        code = None if failures is None else failures.get("nonzero")
        if code is None:
            code = "execution_error"
        raise error_type(
            _error_outcome(
                outcome_type=error_type,
                status=code,
                summary="Command returned non-zero exit status",
                diagnostic_code="operation.command_failed",
                diagnostic_message="Command returned non-zero exit status",
                details={"reference": reference, "returncode": completed.returncode},
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


def _error_outcome(
    *,
    outcome_type: type[MappedOutcomeError] | type[MappedBootstrapError],
    status: str,
    summary: str,
    diagnostic_code: str,
    diagnostic_message: str,
    details: JSONObject,
    raw: JSONObject,
) -> OperationOutcome | BootstrapOutcome:
    diagnostics = (
        Diagnostic(
            code=diagnostic_code,
            level="error",
            message=diagnostic_message,
            details=details,
        ),
    )
    if outcome_type is MappedBootstrapError:
        return BootstrapOutcome(status=status, summary=summary, diagnostics=diagnostics, raw=raw)
    return OperationOutcome(status=status, summary=summary, diagnostics=diagnostics, raw=raw)
