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


@dataclass(frozen=True, slots=True)
class NegativeRuleSpec:
    """Published negative rule for a covered authoring surface."""

    name: str
    surface: str
    rule: str
    reason: str
    related_codes: tuple[str, ...] = ()

    def to_contract(self) -> JSONObject:
        return {
            "name": self.name,
            "surface": self.surface,
            "rule": self.rule,
            "reason": self.reason,
            "related_codes": list(self.related_codes),
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

NEGATIVE_RULES: tuple[NegativeRuleSpec, ...] = (
    NegativeRuleSpec(
        name="guard_expression.no_state_root",
        surface="guard_expression",
        rule="State references are not allowed in guard expressions",
        reason="guards run before steps and only support input references and public probe references",
    ),
    NegativeRuleSpec(
        name="guard_expression.no_filters",
        surface="guard_expression",
        rule="Value-expression filters are not allowed in guard expressions",
        reason="guard expressions are a distinct probe/input language and do not evaluate value-expression filter pipelines",
    ),
    NegativeRuleSpec(
        name="guard_expression.no_format_builtin",
        surface="guard_expression",
        rule="The format builtin is not allowed in guard expressions",
        reason="guard expressions do not evaluate value-expression builtins",
    ),
    NegativeRuleSpec(
        name="workflow_step.exactly_one_form",
        surface="workflow_step",
        rule="A workflow step must define exactly one of uses, state_set, or state_delete",
        reason="step forms are mutually exclusive in the workflow contract",
        related_codes=("validation.workflow.step.form",),
    ),
    NegativeRuleSpec(
        name="workflow_step.with_requires_uses",
        surface="workflow_step",
        rule="The with field is allowed only together with uses",
        reason="runtime value inputs belong to operation-call step form only",
        related_codes=("validation.workflow.step.with_without_uses",),
    ),
    NegativeRuleSpec(
        name="state_set.single_target_entry",
        surface="state_set",
        rule="state_set must contain exactly one target entry",
        reason="each state-set step writes one resolved state target at a time",
        related_codes=("validation.workflow.state_set.entry_count",),
    ),
    NegativeRuleSpec(
        name="format_value.args_must_be_list",
        surface="value_expression.format_object",
        rule="format-object args must be a list when provided",
        reason="format object arguments are evaluated positionally",
        related_codes=("validation.workflow.value_expr.format.args_type",),
    ),
)
