"""Preflight step classification helpers."""

from __future__ import annotations

from typing import Literal

from ordo.model.workflow import Step

from .resolution import ResolvedBuiltinStep, ResolvedOperation, ResolvedRunStep, ResolvedStep

PreflightStepClassification = Literal[
    "read_only_analyzable",
    "read_only_unanalyzable",
    "effectful",
    "context_only",
    "unknown",
]


def classify_preflight_step(step: Step, resolved_step: ResolvedStep | None = None) -> PreflightStepClassification:
    """Return the conservative preflight classification for one step."""

    if resolved_step is not None:
        if isinstance(resolved_step, ResolvedOperation):
            if resolved_step.connector_namespace == "routine" and resolved_step.operation.kind == "probe":
                return "read_only_unanalyzable"
            return "read_only_analyzable" if resolved_step.operation.kind == "probe" else "effectful"
        if isinstance(resolved_step, ResolvedBuiltinStep):
            return _classify_builtin_name(resolved_step.builtin)
        if isinstance(resolved_step, ResolvedRunStep):
            return "read_only_unanalyzable"

    if step.operation is not None:
        return "unknown"
    if step.value is not None:
        return "read_only_analyzable"
    if step.profile_switch is not None:
        return "context_only"
    if step.state_set is not None or step.state_delete is not None:
        return "effectful"
    if step.run is not None or step.steps is not None:
        return "read_only_unanalyzable"
    return "unknown"


def _classify_builtin_name(builtin: str) -> PreflightStepClassification:
    if builtin in {"value", "result", "publish"}:
        return "read_only_analyzable"
    if builtin == "checkpoint":
        return "read_only_analyzable"
    if builtin == "profile_switch":
        return "context_only"
    if builtin in {"state_set", "state_delete"}:
        return "effectful"
    return "unknown"
