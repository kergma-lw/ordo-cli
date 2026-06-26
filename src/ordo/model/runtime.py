"""Runtime planning and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .diagnostic import Diagnostic
from .json import JSONObject


class Mode(StrEnum):
    """Baseline runtime modes promised by the v0 contract."""

    CHECK = "check"
    PLAN = "plan"
    EXECUTE = "execute"
    EXPLAIN = "explain"


class RuntimeStatus(StrEnum):
    """Baseline runtime statuses exposed to humans and agents."""

    OK = "ok"
    GUARD_FAILED = "guard_failed"
    VALIDATION_ERROR = "validation_error"
    RESOLUTION_ERROR = "resolution_error"
    EXECUTION_ERROR = "execution_error"


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Structured plan surface for workflow evaluation and execution intent."""

    guard_checks: tuple[str, ...] = ()
    step_names: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OperationResult:
    """Structured connector operation outcome."""

    status: str
    summary: str | None = None
    observations: JSONObject = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
    raw: JSONObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    """JSON-shaped workflow runtime result envelope."""

    mode: Mode
    status: RuntimeStatus
    diagnostics: tuple[Diagnostic, ...] = ()
    plan: ExecutionPlan | None = None
    outputs: JSONObject = field(default_factory=dict)
    operation_results: tuple[OperationResult, ...] = ()
    failed_guard: str | None = None
    failed_step: str | None = None


ExecutionResult = RuntimeResult
