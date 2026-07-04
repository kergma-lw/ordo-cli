"""Canonical runtime-owned metadata for capabilities and expression surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ordo.model.json import JSONObject

from .value_expressions import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS

CapabilityStatus = Literal["supported", "unsupported", "planned"]


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """Published capability state for a runtime-visible surface."""

    name: str
    status: CapabilityStatus
    scope: str

    def to_contract(self) -> JSONObject:
        return {"name": self.name, "status": self.status, "scope": self.scope}


@dataclass(frozen=True, slots=True)
class ExpressionRootSpec:
    """Canonical metadata for one published expression root."""

    name: str
    surfaces: tuple[str, ...]

    def to_contract(self) -> JSONObject:
        return {"name": self.name, "surfaces": list(self.surfaces)}


@dataclass(frozen=True, slots=True)
class ExpressionSurfaceSpec:
    """Canonical metadata for one published expression surface."""

    name: str
    roots: tuple[str, ...]
    filters: tuple[str, ...] = ()
    builtins: tuple[str, ...] = ()

    def to_contract(self) -> JSONObject:
        return {
            "name": self.name,
            "roots": list(self.roots),
            "filters": list(self.filters),
            "builtins": list(self.builtins),
        }


RUNTIME_CAPABILITIES: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(name="workflow.value_expressions", status="supported", scope="workflow"),
    CapabilitySpec(name="workflow.state_needs", status="supported", scope="workflow"),
    CapabilitySpec(name="workflow.state_bindings", status="supported", scope="workflow"),
    CapabilitySpec(name="workflow.step.state_set", status="supported", scope="workflow.step"),
    CapabilitySpec(name="workflow.step.state_delete", status="supported", scope="workflow.step"),
    CapabilitySpec(name="workflow.step.condition", status="unsupported", scope="workflow.step"),
    CapabilitySpec(name="workflow.step.register", status="unsupported", scope="workflow.step"),
    CapabilitySpec(name="workflow.step.outputs", status="unsupported", scope="workflow.step"),
    CapabilitySpec(name="workflow.branching", status="unsupported", scope="workflow"),
)

EXPRESSION_ROOTS: tuple[ExpressionRootSpec, ...] = (
    ExpressionRootSpec(name="inputs", surfaces=("guard_expression", "state_key_reference", "value_expression")),
    ExpressionRootSpec(name="probe", surfaces=("guard_expression",)),
    ExpressionRootSpec(name="state", surfaces=("value_expression",)),
)

EXPRESSION_SURFACES: tuple[ExpressionSurfaceSpec, ...] = (
    ExpressionSurfaceSpec(name="guard_expression", roots=("inputs", "probe")),
    ExpressionSurfaceSpec(
        name="value_expression",
        roots=("inputs", "state"),
        filters=tuple(VALUE_EXPRESSION_FILTERS),
        builtins=tuple(VALUE_EXPRESSION_BUILTINS),
    ),
    ExpressionSurfaceSpec(name="state_key_reference", roots=("inputs",)),
)
