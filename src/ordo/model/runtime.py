"""Runtime planning and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .diagnostic import Diagnostic
from .json import JSONObject, JSONValue


@dataclass(frozen=True, slots=True)
class PreflightGuardNode:
    """Internal structured guard coverage node for preflight reasoning."""

    reference: str
    block_index: int
    relevant: bool
    evaluated: bool
    status: str
    unknown_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PreflightBlockNode:
    """Internal structured block node for preflight reasoning."""

    block_index: int
    block_type: str
    status: str
    active_profile: str | None = None
    guard_references: tuple[str, ...] = ()
    step_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreflightDecisionModel:
    """Internal reusable workflow-shaped preflight model."""

    allowed_state: str
    analysis_complete: bool
    incomplete_reasons: tuple[str, ...] = ()
    guard_nodes: tuple[PreflightGuardNode, ...] = ()
    block_nodes: tuple[PreflightBlockNode, ...] = ()


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

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped plan form."""

        return {
            "guard_checks": list(self.guard_checks),
            "step_names": list(self.step_names),
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class OperationResult:
    """Structured connector operation outcome."""

    status: str
    summary: str | None = None
    outputs: JSONObject = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
    raw: JSONObject = field(default_factory=dict)

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped operation result form."""

        return {
            "status": self.status,
            "summary": self.summary,
            "outputs": dict(self.outputs),
            "diagnostics": [diagnostic.to_contract() for diagnostic in self.diagnostics],
            "raw": dict(self.raw),
        }


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    """JSON-shaped workflow runtime result envelope."""

    mode: Mode
    status: RuntimeStatus
    diagnostics: tuple[Diagnostic, ...] = ()
    plan: ExecutionPlan | None = None
    outputs: JSONObject = field(default_factory=dict)
    results: tuple[JSONValue, ...] = ()
    published: tuple[JSONValue, ...] = ()
    operation_results: tuple[OperationResult, ...] = ()
    failed_guard: str | None = None
    failed_step: str | None = None
    preflight_decision: PreflightDecisionModel | None = None

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped runtime result contract."""

        return {
            "mode": self.mode.value,
            "status": self.status.value,
            "diagnostics": [diagnostic.to_contract() for diagnostic in self.diagnostics],
            "plan": None if self.plan is None else self.plan.to_contract(),
            "outputs": dict(self.outputs),
            "results": list(self.results),
            "published": list(self.published),
            "operation_results": [result.to_contract() for result in self.operation_results],
            "failed_guard": self.failed_guard,
            "failed_step": self.failed_step,
        }


ExecutionResult = RuntimeResult
