"""Canonical runtime-owned metadata for capabilities and expression surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ordo.model.json import JSONObject

from .local_expression_engine.core import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS

CapabilityStatus = Literal["supported", "unsupported", "planned"]


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """Published capability state for a runtime-visible surface."""

    name: str
    status: CapabilityStatus
    scope: str
    related_capabilities: tuple[str, ...] = ()
    related_negative_rules: tuple[str, ...] = ()
    related_model_nodes: tuple[str, ...] = ()
    must_not_infer: tuple[str, ...] = ()

    def to_contract(self) -> JSONObject:
        return {
            "name": self.name,
            "status": self.status,
            "scope": self.scope,
            "related_capabilities": list(self.related_capabilities),
            "related_negative_rules": list(self.related_negative_rules),
            "related_model_nodes": list(self.related_model_nodes),
            "must_not_infer": list(self.must_not_infer),
        }


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
    boolean_operators: tuple[str, ...] = ()

    def to_contract(self) -> JSONObject:
        return {
            "name": self.name,
            "roots": list(self.roots),
            "filters": list(self.filters),
            "builtins": list(self.builtins),
            "boolean_operators": list(self.boolean_operators),
        }


@dataclass(frozen=True, slots=True)
class NegativeRuleSpec:
    """Published negative rule for a covered authoring surface."""

    name: str
    surface: str
    rule: str
    reason: str
    related_codes: tuple[str, ...] = ()
    related_capabilities: tuple[str, ...] = ()
    related_model_nodes: tuple[str, ...] = ()

    def to_contract(self) -> JSONObject:
        return {
            "name": self.name,
            "surface": self.surface,
            "rule": self.rule,
            "reason": self.reason,
            "related_codes": list(self.related_codes),
            "related_capabilities": list(self.related_capabilities),
            "related_model_nodes": list(self.related_model_nodes),
        }


RUNTIME_CAPABILITIES: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(name="workflow.local_expressions", status="supported", scope="workflow"),
    CapabilitySpec(
        name="workflow.include_fragments",
        status="supported",
        scope="workflow",
        related_capabilities=("workflow.local_expressions", "workflow.step.register"),
        related_model_nodes=(
            "workflow.include_contract",
            "workflow.include",
            "workflow.include.with",
            "workflow.fragment.description",
            "workflow.fragment.args",
            "workflow.local_expression_root.args",
        ),
    ),
    CapabilitySpec(name="workflow.state_needs", status="supported", scope="workflow"),
    CapabilitySpec(name="workflow.state_bindings", status="supported", scope="workflow"),
    CapabilitySpec(name="workflow.step.state_set", status="supported", scope="workflow.step"),
    CapabilitySpec(name="workflow.step.state_delete", status="supported", scope="workflow.step"),
    CapabilitySpec(name="workflow.step.value", status="supported", scope="workflow.step"),
    CapabilitySpec(
        name="runtime.launchers",
        status="supported",
        scope="runtime",
        related_capabilities=("workflow.step.launcher",),
        related_negative_rules=("workflow_step.launcher_requires_uses",),
        related_model_nodes=("profile.launchers", "workflow.step.launcher", "workflow.step_forms.operation_call"),
    ),
    CapabilitySpec(
        name="workflow.step.launcher",
        status="supported",
        scope="workflow.step",
        related_capabilities=("runtime.launchers",),
        related_negative_rules=("workflow_step.launcher_requires_uses",),
        related_model_nodes=("workflow.step.launcher", "profile.launchers", "workflow.step_forms.operation_call"),
    ),
    CapabilitySpec(
        name="workflow.step.condition",
        status="supported",
        scope="workflow.step",
        related_capabilities=("workflow.step.register", "workflow.step.value"),
        related_negative_rules=("workflow_step.if_conflicts_with_register",),
        related_model_nodes=("workflow.step.if", "workflow.step.register", "workflow.step_forms.operation_call", "workflow.step_forms.value"),
    ),
    CapabilitySpec(
        name="workflow.step.register",
        status="supported",
        scope="workflow.step",
        related_capabilities=("workflow.step.condition", "workflow.step.outputs", "workflow.step.value"),
        related_negative_rules=("workflow_step.register_requires_uses", "workflow_step.if_conflicts_with_register"),
        related_model_nodes=("workflow.step.register", "workflow.step.uses", "workflow.step.value", "workflow.step_forms.operation_call", "workflow.step_forms.value"),
    ),
    CapabilitySpec(name="workflow.step.outputs", status="supported", scope="workflow.step"),
    CapabilitySpec(
        name="workflow.branching",
        status="supported",
        scope="workflow",
        related_capabilities=("workflow.step.condition", "workflow.step.register", "workflow.step.value"),
        related_negative_rules=("workflow_step.if_conflicts_with_register",),
        related_model_nodes=("workflow.step.if", "workflow.step.register", "workflow.step_forms.operation_call", "workflow.step_forms.value"),
    ),
)

EXPRESSION_ROOTS: tuple[ExpressionRootSpec, ...] = (
    ExpressionRootSpec(name="inputs", surfaces=("guard_expression", "state_key_reference", "step_condition", "embedded_value_expression")),
    ExpressionRootSpec(name="probe", surfaces=("guard_expression", "step_condition", "embedded_value_expression")),
    ExpressionRootSpec(name="args", surfaces=("step_condition", "embedded_value_expression")),
    ExpressionRootSpec(name="state", surfaces=("guard_expression", "step_condition", "embedded_value_expression")),
    ExpressionRootSpec(name="step", surfaces=("step_condition", "embedded_value_expression")),
)

EXPRESSION_SURFACES: tuple[ExpressionSurfaceSpec, ...] = (
    ExpressionSurfaceSpec(name="guard_expression", roots=("inputs", "probe", "state"), boolean_operators=("and", "or", "not", "parentheses")),
    ExpressionSurfaceSpec(
        name="step_condition",
        roots=("inputs", "args", "state", "step", "probe"),
        filters=tuple(VALUE_EXPRESSION_FILTERS),
        builtins=tuple(VALUE_EXPRESSION_BUILTINS),
        boolean_operators=("and", "or", "not", "parentheses"),
    ),
    ExpressionSurfaceSpec(
        name="embedded_value_expression",
        roots=("inputs", "args", "state", "step", "probe"),
        filters=tuple(VALUE_EXPRESSION_FILTERS),
        builtins=tuple(VALUE_EXPRESSION_BUILTINS),
        boolean_operators=("and", "or", "not", "parentheses"),
    ),
    ExpressionSurfaceSpec(name="state_key_reference", roots=("inputs",)),
)

NEGATIVE_RULES: tuple[NegativeRuleSpec, ...] = (
    NegativeRuleSpec(
        name="guard_expression.no_step_root",
        surface="guard_expression",
        rule="Registered step references are not allowed in guard expressions",
        reason="guards run before effectful step execution and therefore cannot depend on registered step results",
        related_codes=("validation.workflow.local_expression.guard.step_ref",),
    ),
    NegativeRuleSpec(
        name="guard_expression.no_filters",
        surface="guard_expression",
        rule="Local-expression filter pipelines are not allowed in guard expressions",
        reason="the shared local-expression engine keeps filter pipelines context-gated, and guard context does not currently evaluate them",
    ),
    NegativeRuleSpec(
        name="guard_expression.no_format_builtin",
        surface="guard_expression",
        rule="The format local-expression builtin is not allowed in guard expressions",
        reason="the shared local-expression engine keeps built-in value construction context-gated, and guard context does not currently evaluate them",
    ),
    NegativeRuleSpec(
        name="workflow_step.exactly_one_form",
        surface="workflow_step",
        rule="A workflow step must define exactly one of uses, value, state_set, or state_delete",
        reason="step forms are mutually exclusive in the workflow contract",
        related_codes=("validation.workflow.step.form",),
    ),
    NegativeRuleSpec(
        name="workflow_step.with_requires_uses",
        surface="workflow_step",
        rule="The with field is allowed only together with uses",
        reason="runtime value inputs belong to operation-call step form only",
        related_codes=("validation.workflow.step.with_without_uses",),
        related_model_nodes=("workflow.step.with", "workflow.step.uses", "workflow.step_forms.operation_call"),
    ),
    NegativeRuleSpec(
        name="workflow_step.launcher_requires_uses",
        surface="workflow_step",
        rule="The launcher field is allowed only together with uses",
        reason="launcher selection wraps operation-call execution surfaces rather than builtin value or state steps",
        related_codes=("validation.workflow.step.launcher_without_uses",),
        related_capabilities=("runtime.launchers", "workflow.step.launcher"),
        related_model_nodes=("workflow.step.launcher", "workflow.step.uses", "workflow.step_forms.operation_call"),
    ),
    NegativeRuleSpec(
        name="workflow_step.register_requires_uses",
        surface="workflow_step",
        rule="The register field is allowed only together with uses or value",
        reason="the MVP publishes registered step results only for operation-call steps and pure value steps",
        related_codes=("validation.workflow.step.register_without_uses",),
        related_capabilities=("workflow.step.register", "workflow.step.value"),
        related_model_nodes=("workflow.step.register", "workflow.step.uses", "workflow.step.value", "workflow.step_forms.operation_call", "workflow.step_forms.value"),
    ),
    NegativeRuleSpec(
        name="workflow_step.if_conflicts_with_register",
        surface="workflow_step",
        rule="The if and register fields cannot be used together in the MVP",
        reason="the MVP avoids publishing synthetic registered step results for skipped conditional steps",
        related_codes=("validation.workflow.step.if_with_register",),
        related_capabilities=("workflow.step.condition", "workflow.step.register", "workflow.step.value", "workflow.branching"),
        related_model_nodes=("workflow.step.if", "workflow.step.register", "workflow.step_forms.operation_call", "workflow.step_forms.value"),
    ),
    NegativeRuleSpec(
        name="embedded_value_expression.step_refs_must_be_backward",
        surface="embedded_value_expression",
        rule="Registered step references may target only earlier steps in the same workflow",
        reason="step-result reads are order-sensitive execution-local data flow rather than random access workflow state",
        related_codes=("validation.workflow.step_ref.forward",),
    ),
    NegativeRuleSpec(
        name="state_set.single_target_entry",
        surface="state_set",
        rule="state_set must contain exactly one target entry",
        reason="each state-set step writes one resolved state target at a time",
        related_codes=("validation.workflow.state_set.entry_count",),
    ),
    NegativeRuleSpec(
        name="workflow_fragment.no_state_surface",
        surface="workflow.include_fragments",
        rule="Included fragments must not read, declare, or mutate runtime state",
        reason="runtime state remains a top-level workflow handoff surface rather than reusable fragment-local memory",
        related_codes=("load.workflow.include.state_forbidden",),
    ),
    NegativeRuleSpec(
        name="workflow_state_role.write_after_last_read",
        surface="workflow.state_needs",
        rule="Logical state role writes and deletes are allowed only after the final read of that same role",
        reason="persistent runtime state should capture final cross-run handoff rather than per-run scratch flow",
        related_codes=("validation.workflow.state_role.write_before_last_read",),
    ),
    NegativeRuleSpec(
        name="format_value.args_must_be_list",
        surface="embedded_value_expression.format_object",
        rule="format-object args must be a list when provided",
        reason="format object arguments are evaluated positionally",
        related_codes=("validation.workflow.value_expr.format.args_type",),
    ),
)
