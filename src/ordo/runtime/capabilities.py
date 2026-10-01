"""Canonical runtime-owned metadata for capabilities and expression surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ordo.model.json import JSONObject
from ordo.model.human import HumanDeclaration, declare_human, human_content

from .local_expression_engine.core import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS

CapabilityStatus = Literal["supported", "unsupported", "planned", "deprecated"]


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
    human: HumanDeclaration | JSONObject | None = None

    def human_declaration(self) -> HumanDeclaration:
        if isinstance(self.human, HumanDeclaration):
            return self.human
        if self.human is not None:
            return declare_human(self.human)  # type: ignore[arg-type]
        return declare_human({
            "title": _CAPABILITY_TITLES[self.name],
            "goal": f"Understand whether {self.name} is available for workflow authoring.",
            "summary": f"This surface is {self.status}.",
            "sections": [
                *([{"heading": "Do not infer", "items": list(self.must_not_infer)}] if self.must_not_infer else []),
            ],
        })

    def to_contract(self) -> JSONObject:
        return {
            "name": self.name,
            "status": self.status,
            "scope": self.scope,
            "related_capabilities": list(self.related_capabilities),
            "related_negative_rules": list(self.related_negative_rules),
            "related_model_nodes": list(self.related_model_nodes),
            "must_not_infer": list(self.must_not_infer),
            "human": human_content(self.human_declaration(), owner=self.name),
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
    human: HumanDeclaration | JSONObject | None = None

    def human_declaration(self) -> HumanDeclaration:
        if isinstance(self.human, HumanDeclaration):
            return self.human
        if self.human is not None:
            return declare_human(self.human)  # type: ignore[arg-type]
        return declare_human({
            "title": _NEGATIVE_RULE_TITLES[self.name],
            "goal": "Avoid an invalid workflow shape before it reaches execution.",
            "summary": self.rule,
            "sections": [
                {"heading": "Why", "items": [self.reason]},
            ],
        })

    def to_contract(self) -> JSONObject:
        return {
            "name": self.name,
            "surface": self.surface,
            "rule": self.rule,
            "reason": self.reason,
            "related_codes": list(self.related_codes),
            "related_capabilities": list(self.related_capabilities),
            "related_model_nodes": list(self.related_model_nodes),
            "human": human_content(self.human_declaration(), owner=self.name),
        }


RUNTIME_CAPABILITIES: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        name="workflow.local_expressions",
        status="supported",
        scope="workflow",
        related_model_nodes=(
            "workflow.local_expression.filter",
            "workflow.local_expression.builtin",
            "workflow.local_expression.adapter",
        ),
    ),
    CapabilitySpec(
        name="workflow.local_expression.adapter",
        status="supported",
        scope="workflow",
        related_capabilities=("workflow.local_expressions",),
        related_model_nodes=(
            "workflow.local_expression.adapter_seam",
            "workflow.local_expression.adapter_binding",
            "workflow.local_expression.adapter.json",
            "workflow.local_expression.adapter.key_value",
            "workflow.local_expression.adapter.markdown",
            "workflow.local_expression.adapter.text",
            "workflow.local_expression.adapter.yaml",
        ),
    ),
    CapabilitySpec(
        name="workflow.state_bindings",
        status="supported",
        scope="workflow",
        related_model_nodes=(
            "playbook.states",
            "state.workflow_surface.state_binding_field",
            "state.workflow_surface.storage_targets_field",
            "workflow.step.state_set",
            "workflow.step.state_delete",
        ),
    ),
    CapabilitySpec(
        name="workflow.state_needs",
        status="supported",
        scope="workflow",
        related_capabilities=("workflow.state_bindings",),
        related_model_nodes=(
            "state.workflow_surface.state_needs_field",
            "playbook.states",
            "state.workflow_surface.state_binding_field",
        ),
    ),
    CapabilitySpec(
        name="workflow.step.state_set",
        status="supported",
        scope="workflow.step",
        related_capabilities=("workflow.state_bindings",),
        related_model_nodes=(
            "state.workflow_surface.step_state_set_field",
            "workflow.step_forms.state_set",
            "workflow.state_needs",
            "workflow.state_bindings",
        ),
        related_negative_rules=("state_set.single_target_entry",),
    ),
    CapabilitySpec(
        name="workflow.step.state_delete",
        status="supported",
        scope="workflow.step",
        related_capabilities=("workflow.state_bindings",),
        related_model_nodes=(
            "state.workflow_surface.step_state_delete_field",
            "workflow.step_forms.state_delete",
        ),
    ),
    CapabilitySpec(
        name="workflow.step.value",
        status="supported",
        scope="workflow.step",
        related_capabilities=("workflow.local_expressions",),
        related_model_nodes=(
            "workflow.step_forms.value",
            "workflow.step.result",
            "workflow.step.publish",
        ),
    ),
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
    CapabilitySpec(
        name="runtime.launchers",
        status="deprecated",
        scope="runtime",
        related_capabilities=("workflow.step.launcher",),
        related_negative_rules=("workflow_step.launcher_requires_uses",),
        related_model_nodes=("profile.launchers", "workflow.step.launcher", "workflow.step_forms.operation_call"),
        must_not_infer=(
            "launcher support means launcher-centric workflow authoring is still preferred",
            "a launcher is safer than a published routine by default",
        ),
    ),
    CapabilitySpec(
        name="workflow.step.launcher",
        status="deprecated",
        scope="workflow.step",
        related_capabilities=("runtime.launchers",),
        related_negative_rules=("workflow_step.launcher_requires_uses",),
        related_model_nodes=("workflow.step.launcher", "profile.launchers", "workflow.step_forms.operation_call"),
        must_not_infer=(
            "step-level launcher selection is a preferred new authoring path",
            "launchers should be chosen over routine publication for new project-local automation",
        ),
    ),
    CapabilitySpec(
        name="workflow.step.condition",
        status="supported",
        scope="workflow.step",
        related_capabilities=("workflow.step.register", "workflow.step.value"),
        related_negative_rules=("workflow_step.if_conflicts_with_register", "workflow_step.gate_conflicts_with_register"),
        related_model_nodes=("workflow.step.if", "workflow.step.gate", "workflow.step.register", "workflow.step_forms.operation_call", "workflow.step_forms.gate_checkpoint", "workflow.step_forms.value"),
        must_not_infer=(
            "one shared boolean condition surface means if and gate do the same semantic job",
            "if is the catch-all control mechanism for applicability, admission, and local branching",
        ),
    ),
    CapabilitySpec(
        name="workflow.step.register",
        status="supported",
        scope="workflow.step",
        related_capabilities=("workflow.step.condition", "workflow.step.outputs", "workflow.step.value"),
        related_negative_rules=("workflow_step.register_requires_uses", "workflow_step.if_conflicts_with_register", "workflow_step.gate_conflicts_with_register"),
        related_model_nodes=("workflow.step.register", "workflow.step.uses", "workflow.step.value", "workflow.step_forms.operation_call", "workflow.step_forms.value"),
    ),
    CapabilitySpec(
        name="workflow.step.outputs",
        status="supported",
        scope="workflow.step",
        related_capabilities=("workflow.step.register", "workflow.step.value"),
        related_model_nodes=("workflow.step.name", "workflow.step.register", "workflow.step.value", "workflow.step_forms.operation_call", "workflow.step_forms.run_invocation"),
        must_not_infer=(
            "step outputs are ambient global context instead of explicit reads from named or registered steps",
        ),
    ),
    CapabilitySpec(
        name="workflow.branching",
        status="supported",
        scope="workflow",
        related_capabilities=("workflow.step.condition", "workflow.step.register", "workflow.step.value"),
        related_negative_rules=("workflow_step.if_conflicts_with_register",),
        related_model_nodes=("workflow.step.if", "workflow.step.register", "workflow.step_forms.operation_call", "workflow.step_forms.value"),
        must_not_infer=(
            "branching support means if should carry workflow applicability or admission decisions",
            "workflow branching is best modeled by stretching if across every conditional concern",
        ),
    ),
)

EXPRESSION_ROOTS: tuple[ExpressionRootSpec, ...] = (
    ExpressionRootSpec(name="inputs", surfaces=("guard_expression", "state_key_expression", "step_condition", "embedded_value_expression")),
    ExpressionRootSpec(name="probe", surfaces=("guard_expression", "step_condition", "embedded_value_expression")),
    ExpressionRootSpec(name="args", surfaces=("step_condition", "embedded_value_expression")),
    ExpressionRootSpec(name="item", surfaces=("step_condition", "embedded_value_expression", "include_binding_expression")),
    ExpressionRootSpec(name="state", surfaces=("guard_expression", "step_condition", "embedded_value_expression")),
    ExpressionRootSpec(name="step", surfaces=("step_condition", "embedded_value_expression")),
)

EXPRESSION_SURFACES: tuple[ExpressionSurfaceSpec, ...] = (
    ExpressionSurfaceSpec(
        name="guard_expression",
        roots=("inputs", "probe", "state"),
        filters=tuple(VALUE_EXPRESSION_FILTERS),
        builtins=tuple(VALUE_EXPRESSION_BUILTINS),
        boolean_operators=("and", "or", "not", "parentheses"),
    ),
    ExpressionSurfaceSpec(
        name="step_condition",
        roots=("inputs", "args", "item", "state", "step", "probe"),
        filters=tuple(VALUE_EXPRESSION_FILTERS),
        builtins=tuple(VALUE_EXPRESSION_BUILTINS),
        boolean_operators=("and", "or", "not", "parentheses"),
    ),
    ExpressionSurfaceSpec(
        name="embedded_value_expression",
        roots=("inputs", "args", "item", "state", "step", "probe"),
        filters=tuple(VALUE_EXPRESSION_FILTERS),
        builtins=tuple(VALUE_EXPRESSION_BUILTINS),
        boolean_operators=("and", "or", "not", "parentheses"),
    ),
    ExpressionSurfaceSpec(
        name="include_binding_expression",
        roots=("inputs", "item", "state", "step", "probe"),
        filters=tuple(VALUE_EXPRESSION_FILTERS),
        builtins=tuple(VALUE_EXPRESSION_BUILTINS),
        boolean_operators=("and", "or", "not", "parentheses"),
    ),
    ExpressionSurfaceSpec(
        name="state_key_expression",
        roots=("inputs", "args", "item", "state", "step"),
        filters=tuple(VALUE_EXPRESSION_FILTERS),
        builtins=tuple(VALUE_EXPRESSION_BUILTINS),
        boolean_operators=("and", "or", "not", "parentheses"),
    ),
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
        name="guard_expression.no_adapter_write_path",
        surface="guard_expression",
        rule="Representation-adapter write paths such as '->...' are not allowed in guard expressions",
        reason="guard expressions may use read-only local-expression constructs but must remain pure and pre-execution-safe",
    ),
    NegativeRuleSpec(
        name="guard_expression.boolean_result_required",
        surface="guard_expression",
        rule="Guard expressions must evaluate to a boolean result",
        reason="guard success and failure are defined by boolean policy outcomes rather than arbitrary value production",
    ),
    NegativeRuleSpec(
        name="workflow_step.exactly_one_form",
        surface="workflow_step",
        rule="A workflow step must define exactly one of uses, run, steps, profile_switch, value, result, publish, state_set, or state_delete; a standalone gate checkpoint is the exception",
        reason="primary step forms are mutually exclusive in the workflow contract",
        related_codes=("validation.workflow.step.form",),
    ),
    NegativeRuleSpec(
        name="workflow_step.with_requires_uses",
        surface="workflow_step",
        rule="The with field is allowed only together with uses or run",
        reason="runtime value inputs belong to operation-call and named-run step forms",
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
        rule="The register field is allowed only together with uses, run, or value",
        reason="Only operation-call steps, reusable run invocations, and value steps produce results that can be named for later reads",
        related_codes=("validation.workflow.step.register_without_uses",),
        related_capabilities=("workflow.step.register", "workflow.step.value", "workflow.step.run"),
        related_model_nodes=("workflow.step.register", "workflow.step.uses", "workflow.step.run", "workflow.step.value", "workflow.step_forms.operation_call", "workflow.step_forms.run_invocation", "workflow.step_forms.value"),
    ),
    NegativeRuleSpec(
        name="workflow_step.if_conflicts_with_register",
        surface="workflow_step",
        rule="The if and register fields cannot be used together",
        reason="A skipped optional step has no result to name for later reads",
        related_codes=("validation.workflow.step.if_with_register",),
        related_capabilities=("workflow.step.condition", "workflow.step.register", "workflow.step.value", "workflow.branching"),
        related_model_nodes=("workflow.step.if", "workflow.step.register", "workflow.step_forms.operation_call", "workflow.step_forms.value"),
    ),
    NegativeRuleSpec(
        name="workflow_step.gate_conflicts_with_register",
        surface="workflow_step",
        rule="The gate and register fields cannot be used together; split the gate into a standalone checkpoint step before the registered step",
        reason="gate admission should stay separate from step-result publication so blocked steps never need to imply a registered output surface",
        related_codes=("validation.workflow.step.gate_register_conflict", "load.step.gate_register_conflict"),
        related_capabilities=("workflow.step.condition", "workflow.step.register", "workflow.step.value"),
        related_model_nodes=("workflow.step.gate", "workflow.step.register", "workflow.step_forms.gate_checkpoint", "workflow.step_forms.operation_call", "workflow.step_forms.value"),
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
        rule="Before binding, logical state role writes and deletes are allowed only after the final read of that same role; bound validation instead compares actual storage in each access context",
        reason="persistent runtime state should capture final cross-run handoff rather than per-run scratch flow",
        related_codes=("validation.workflow.state_role.write_before_last_read",),
    ),
    NegativeRuleSpec(
        name="workflow_state_storage.write_after_last_read",
        surface="workflow.state_bindings",
        rule="After binding, write or delete only after the final read of the same actual file, regardless of role, state name, profile, key, or field",
        reason="relative paths resolve in each access context; normalized paths, symlinks, and existing hardlinks can alias, while the same role may resolve to different files and be valid",
        related_codes=("validation.workflow.state_storage.write_before_last_read",),
    ),
    NegativeRuleSpec(
        name="workflow_state_storage.relevant_identity_required",
        surface="workflow.state_bindings",
        rule="Conservatively reject early only relevant write/later-read pairs whose storage identity cannot be established; this is not a proven ordering violation",
        reason="Checks happen before observations and effects, so uncertain context alone does not reject read-only, read-before-write, or known-disjoint access. Checking one child workflow does not establish safety across separate calls or repeated work.",
        related_codes=("validation.workflow.state_storage.identity_unresolved",),
    ),
    NegativeRuleSpec(
        name="format_value.args_must_be_list",
        surface="embedded_value_expression.format_object",
        rule="format-object args must be a list when provided",
        reason="format object arguments are evaluated positionally",
        related_codes=("validation.workflow.value_expr.format.args_type",),
    ),
)


CAPABILITY_FOCUSED_DESCRIBE_HUMANS: dict[str, HumanDeclaration] = {
    "embedded_value_expression.step_refs_must_be_backward": declare_human({
        "title": "Earlier step results", "goal": "Read a step result only after that step has produced it on the current path.",
        "summary": "Workflow expressions use earlier completed work as inputs; they do not predict later results.",
        "sections": [{"heading": "Contract detail", "items": ["The published validation identifier is `embedded_value_expression.step_refs_must_be_backward`." ]}, {"heading": "Boundary", "items": ["Move the dependent expression after the producing step instead of relying on execution order implicitly."]}],
    }),
    "format_value.args_must_be_list": declare_human({
        "title": "Formatting arguments", "goal": "Provide formatting values in their intended positional order.",
        "summary": "A formatting expression accepts an ordered list of values when it needs arguments.",
        "sections": [{"heading": "Contract detail", "items": ["The published validation identifier is `format_value.args_must_be_list`." ]}, {"heading": "Boundary", "items": ["Do not use an object or scalar where the formatting contract requires a list."]}],
    }),
    "guard_expression.boolean_result_required": declare_human({
        "title": "Guard decision", "goal": "Make workflow applicability resolve to a clear yes-or-no decision.",
        "summary": "A guard accepts a boolean result so readers can see whether the workflow may proceed.",
        "sections": [{"heading": "Contract detail", "items": ["The published validation identifier is `guard_expression.boolean_result_required`." ]}, {"heading": "Boundary", "items": ["Use a value step for data shaping rather than treating an arbitrary value as a guard decision."]}],
    }),
    "guard_expression.no_adapter_write_path": declare_human({
        "title": "Read-only guard adapters", "goal": "Inspect structured content in a guard without changing it.",
        "summary": "Guard expressions may use adapter reads but cannot use adapter update paths.",
        "sections": [{"heading": "Contract detail", "items": ["The published validation identifier is `guard_expression.no_adapter_write_path`." ]}, {"heading": "Boundary", "items": ["Perform changes in an explicit admitted step, not while deciding applicability."]}],
    }),
    "guard_expression.no_step_root": declare_human({
        "title": "Guard inputs", "goal": "Base a workflow guard on information available before the workflow steps run.",
        "summary": "A guard cannot read step output because it decides whether those steps may begin.",
        "sections": [{"heading": "Contract detail", "items": ["The published validation identifier is `guard_expression.no_step_root`." ]}, {"heading": "Boundary", "items": ["Use a later gate when a decision depends on earlier step output."]}],
    }),
    "workflow.local_expressions": declare_human({
        "title": "Local expressions",
        "goal": "Use a small inline expression without hiding workflow behavior.",
        "summary": "Workflow capability for short inline local expressions that only read and reshape already-available input data through workflow roots, pipeline filters, call-style built-in helpers, and representation adapters.",
        "sections": [
            {"heading": "Use when", "items": [
                "A workflow-owned field needs a concise inline read, check, comparison, or small transformation without escalating to a heavier execution surface.",
                "Authoring intent is still local expression shaping rather than external operations, step orchestration, or long opaque helper logic.",
                "The expression may transform input data in subtle ways, but it still stays inside pure local value-shaping rather than changing the outside world.",
            ]},
            {"heading": "Do not use for", "items": [
                "Long, repetitive, or representation-heavy logic that would be clearer through adapters, dedicated workflow structure, or another typed public surface.",
                "Treating local expressions as a catch-all substitute for guards, gates, state surfaces, or other explicit workflow contracts.",
                "Anything that mutates the outside world, performs execution steps, or encodes workflow control flow such as branching, admission, or orchestration.",
            ]},
            {"heading": "Related surfaces", "references": [
                {"handle": "workflow.local_expression.filter", "summary": "Shape one selected value through a pipeline."},
                {"handle": "workflow.local_expression.builtin", "summary": "Use a call-style helper for a check or formatting."},
                {"handle": "workflow.local_expression.adapter", "summary": "Interpret JSON, YAML, Markdown, text, or key-value data."},
            ]},
        ],
    }),
    "workflow.state_bindings": declare_human({
        "title": "State bindings",
        "goal": "Connect declared workflow state roles to durable storage explicitly.",
        "summary": "Workflow capability for binding declared playbook state locations into workflow roles so steps may read, write, or delete durable state explicitly.",
        "sections": [
            {"heading": "Use when", "items": [
                "A workflow needs durable named storage that persists across runs instead of relying on implicit files or transient outputs.",
                "The workflow has already declared state_needs and now must connect those workflow roles to concrete named playbook state locations.",
                "Bind each workflow state role to the named durable location the workflow is allowed to use.",
            ]},
            {"heading": "Do not use for", "items": [
                "Short-lived local values that belong in step outputs, workflow values, or direct inputs rather than declared state storage.",
                "Writing state directly without first binding a declared location into the workflow's explicit state contract.",
                "Assuming different role names create independent storage when they are bound to the same location.",
            ]},
        ],
    }),
    "workflow.state_needs": declare_human({
        "title": "State needs",
        "goal": "Declare durable state requirements before using state steps.",
        "summary": "Workflow capability for declaring which state roles and storage targets the workflow requires before durable state reads, writes, or deletions are valid.",
        "sections": [
            {"heading": "Use when", "items": ["A workflow intends to interact with durable state and must declare that need explicitly before step-level state surfaces become legitimate."]},
            {"heading": "Do not use for", "items": [
                "Binding one concrete role to one declared playbook state location; that next step belongs to workflow.state_bindings.",
                "Implicitly relying on state availability just because a later step mentions state.*; durable state access still needs an explicit workflow need declaration.",
            ]},
        ],
    }),
    "workflow.step.state_delete": declare_human({
        "title": "State delete step",
        "goal": "Delete one no-longer-needed bound state value after its last use.",
        "summary": "Author `state_delete` with one bound state path; when an admitted run reaches the step, that value is removed for later workflow runs.",
        "sections": [
            {"heading": "Before deleting", "items": [
                "Declare the state role with `state_needs`, bind it to a named playbook state location, then set `state_delete` to the one bound path to remove.",
                "Use it only when later workflow runs should no longer see that durable value.",
            ]},
            {"heading": "Ordering and failures", "items": [
                "Place the deletion after every read of the same resolved storage target. Validation rejects a known delete-before-later-read conflict and stops when it cannot establish a relevant target identity safely.",
                "A run removes the value only when it reaches this admitted step. An unbound role, undeclared location, or invalid key prevents the state access instead of deleting an unintended value.",
            ]},
            {"heading": "Do not use for", "items": [
                "Local workflow data cleanup; keep that data in values or registered step outputs.",
                "Writing or reshaping durable state; use workflow.step.state_set when the value should remain available.",
            ]},
            {"heading": "Set up state first", "references": [
                {"handle": "workflow.state_needs", "summary": "Declare the role required by the workflow"},
                {"handle": "workflow.state_bindings", "summary": "Bind the declared role to a playbook state location"},
                {"handle": "workflow.step.state_set", "summary": "Write a durable value instead of removing it"},
            ]},
        ],
    }),
    "workflow.step.value": declare_human({
        "title": "Value step",
        "goal": "Compute one local workflow value without performing an operation.",
        "summary": "Workflow step capability for computing one explicit ephemeral value inside the workflow and optionally registering it for later local reuse.",
        "sections": [
            {"heading": "Use when", "items": ["A step should produce one derived value for later guards, publishes, results, or step-local dataflow without mutating durable state or calling an external operation."]},
            {"heading": "Do not use for", "items": [
                "Durable persistence; use workflow.step.state_set when the value must survive beyond local workflow dataflow.",
                "Outward-facing final result or publication surfaces when the main intent is emitting contract output rather than computing an intermediate value.",
            ]},
        ],
    }),
    "workflow.step.register": declare_human({
        "title": "Register step output",
        "goal": "Give a step result an explicit local name for later reads.",
        "summary": "Workflow step capability for binding one step result to a reusable step-local name so later steps may read that result explicitly.",
        "sections": [
            {"heading": "Use when", "items": [
                "A later step still needs the current step's result through one stable explicit read path such as step.<register>.outputs.value.",
                "The workflow is staging reusable local dataflow rather than emitting one final outward-facing result through publish or result.",
            ]},
            {"heading": "Do not use for", "items": [
                "Outward-facing final result emission; use workflow.step.publish or workflow.step.result when the main intent is final output rather than reuse.",
                "Implicit result reuse without a concrete step-local binding name; register exists to make that reuse path explicit and reviewable.",
            ]},
        ],
    }),
    "workflow.step.condition": declare_human({
        "title": "Step condition",
        "goal": "Make an optional-step or admission decision explicit.",
        "summary": "Workflow step capability for authoring explicit boolean control decisions through step-level if and gate surfaces, where a failed gate blocks the protected execution path.",
        "sections": [
            {"heading": "Use when", "items": [
                "A workflow path needs one explicit step-scoped boolean decision and the real question is whether the step is optional or admitted.",
                "Several predicates should remain reviewable as one declared control surface instead of being hidden inside payload-building expressions.",
            ]},
            {"heading": "Do not use for", "items": [
                "Treating if and gate as interchangeable; if is for optional local branching while gate is for admission decisions.",
                "Whole-workflow applicability or early rejection; that meaning belongs to workflow guards rather than to step-scoped condition surfaces.",
            ]},
        ],
    }),
    "workflow.step.outputs": declare_human({
        "title": "Step outputs",
        "goal": "Read a registered earlier step result explicitly.",
        "summary": "Workflow step capability for reading the explicit output surface of a previously registered step through step.<register>.outputs... paths.",
        "sections": [
            {"heading": "Use when", "items": [
                "A later step, condition, or publication needs one earlier step result through an explicit readable path such as step.issue.outputs.title or step.prepare.outputs.value.",
                "Workflow-local dataflow should stay transient and reviewable instead of being copied into state only to be read again immediately.",
            ]},
            {"heading": "Do not use for", "items": [
                "Pretending every prior step is readable without an explicit register binding; the workflow needs a registered step result to create a durable read path.",
                "Long-term persistence across runs; use declared state surfaces when the data must survive beyond current workflow-local execution.",
            ]},
        ],
    }),
    "workflow.step.state_set": declare_human({
        "title": "State set step",
        "goal": "Persist one bound value for a future workflow run.",
        "summary": "Workflow step capability for writing one explicit value into one bound state target as a deliberate durable state mutation.",
        "sections": [
            {"heading": "Use when", "items": [
                "The workflow must persist one value for a future run after all needed reads are complete.",
                "The workflow has declared and bound the state role used by this step. For `state.shared_state`, first declare `shared_state` in workflow.state_needs, then bind it through workflow.state_bindings to a playbook state location.",
            ]},
            {"heading": "Do not use for", "items": [
                "Ordinary local dataflow that should stay in step outputs or workflow values instead of becoming durable state.",
                "Writing before every read of the same bound storage is complete, even when those reads use different roles, profiles, keys, or fields. Use value + register for per-run reuse.",
                "Writing several unrelated state targets in one step; each state_set step writes exactly one resolved target entry.",
            ]},
            {"heading": "Set up state first", "references": [
                {"handle": "workflow.state_needs", "summary": "Declare the `shared_state` role required by the workflow"},
                {"handle": "workflow.state_bindings", "summary": "Bind that declared role to a playbook state location"},
                {"handle": "playbook.states", "summary": "Declare the named state location used by the binding"},
            ]},
        ],
    }),
    "workflow.include_fragments": declare_human({
        "title": "Included fragments",
        "goal": "Reuse authored structure before the workflow is run.",
        "summary": "Workflow capability for source-time fragment reuse through include expansion with fragment-local args resolved before assembled-workflow validation.",
        "sections": [
            {"heading": "Use when", "items": ["The same authored structure should be reused by expansion into the assembled workflow before execution rather than invoked as a runtime step."]},
            {"heading": "Caller values", "items": [
                "Declare each fragment argument, then bind it through `include.with`. The binding is evaluated in the caller context and may read caller inputs, the current item, state, or an earlier registered step output.",
                "The expanded fragment reads only its declared values as `args.name`; it does not receive every caller value implicitly.",
            ]},
            {"heading": "Do not use for", "items": [
                "Runtime invocation, isolated callee scope, or repeated execution per item; use run surfaces for those runtime behaviors.",
                "Treating include as a hidden control-flow mechanism after execution has already started; include is source-time assembly, not runtime branching.",
            ]},
        ],
    }),
    "workflow.local_expression.adapter": declare_human({
        "title": "Representation adapters",
        "goal": "Transform a value through its published representation.",
        "summary": "Workflow capability for representation-adapter families that project or transform values after a source has already been interpreted as json, yaml, markdown, text, or key-value data.",
        "sections": [
            {"heading": "Use when", "items": ["Inline workflow logic first needs family-owned parsing or structured selection that would be awkward as plain local-expression filters alone."]},
            {"heading": "Choose an adapter", "items": [
                "Use the JSON adapter for JSON structure, the YAML adapter for YAML structure, the Markdown adapter for headings, blocks, lists, or task lists, the text adapter for lines or substrings, and the key-value adapter for key-value text.",
                "Open `workflow.local_expression.adapter.json`, `.yaml`, `.markdown`, `.text`, or `.key_value` for the selected family, then use `workflow.local_expression.adapter_binding` when it needs workflow values.",
            ]},
            {"heading": "Do not use for", "items": [
                "Simple root reads, comparisons, or short pipeline shaping that are already clear with ordinary local-expression filters or builtins.",
                "Assuming an adapter can read workflow values without an explicit `with{...}` binding; supply the values the expression needs.",
            ]},
            {"heading": "Example", "items": ["`json.user.name with{root: inputs.body}` reads a user's name from JSON text supplied by the workflow input."]},
            {"heading": "Related surfaces", "references": [
                {"handle": "workflow.local_expressions", "summary": "Choose ordinary local expressions for direct reads and small shaping."},
                {"handle": "workflow.local_expression.adapter_binding", "summary": "Pass workflow values into adapter syntax explicitly."},
                {"handle": "workflow.local_expression.adapter.json", "summary": "Select or update JSON text by structure."},
            ]},
        ],
    }),
    "runtime.launchers": declare_human({
        "title": "Legacy launchers",
        "goal": "Maintain older launcher-based workflows while moving new work to current surfaces.",
        "summary": "Deprecated runtime capability for honoring legacy launcher-based execution setup when older workflows still reference launcher names at runtime.",
        "sections": [
            {"heading": "Use when", "items": [
                "You are reading or maintaining an older workflow path that still resolves a named launcher through profile.launchers and workflow.step.launcher.",
                "A migration discussion needs to distinguish current compatibility support from the preferred routines-based path for new work.",
            ]},
            {"heading": "Do not use for", "items": [
                "Treating launcher support as approval for new launcher-centric workflow authoring; the capability exists for compatibility, not as the preferred path.",
                "Assuming a runtime capability automatically provides the authored syntax you should introduce next; prefer routines or explicit profile context for new execution setup.",
            ]},
        ],
    }),
    "workflow.step.launcher": declare_human({
        "title": "Legacy launcher step",
        "goal": "Understand an existing launcher selection without introducing it in new workflows.",
        "summary": "Deprecated workflow-step capability for selecting one named legacy launcher record on an operation-shaped step when an older workflow still depends on launcher-based execution setup.",
        "sections": [
            {"heading": "Use when", "items": [
                "You are reading or maintaining an existing workflow that already references one named launcher and need to understand that legacy step surface honestly.",
                "A migration discussion needs to explain how one step-level launcher reference relates to profile.launchers and why routines are now preferred for new local automation.",
            ]},
            {"heading": "Do not use for", "items": [
                "New workflow authoring when a routine or another structured execution-context surface can express the behavior more honestly.",
                "Treating step-level launcher selection as the preferred way to attach execution setup to a step; this capability is deprecated and retained for compatibility only.",
            ]},
            {"heading": "Move forward", "items": ["Keep an existing launcher working by following profile.launchers to the named launcher record and workflow.step.launcher to the operation step that selects it. For new local automation, use the routines alternative and its authoring guidance instead."], "references": [
                {"handle": "profile.launchers", "summary": "Legacy launcher records used by existing workflows"},
                {"handle": "workflow-rules.routine.*", "summary": "When and how to use the supported routines alternative"},
                {"handle": "examples.launcher-step", "summary": "Legacy launcher example for maintenance and migration"},
            ]},
        ],
    }),
    "workflow.version": declare_human({
        "title": "Workflow version",
        "goal": "Declare the workflow document format before its other fields.",
        "summary": "Required top-level workflow format marker that declares which published workflow document shape this file is written against.",
        "sections": [
            {"heading": "Use when", "items": ["Every workflow document must start by declaring the required published workflow format version before workflow, inputs, blocks, or other top-level workflow fields."]},
            {"heading": "Do not use for", "items": [
                "Publishing a domain, release, or business-process version for the workflow itself; this field is only the workflow document-format marker.",
                "Declaring playbook or routine registry document formats; use playbook.version or routine_contract.version for those separate documents.",
            ]},
            {"heading": "Related surfaces", "references": [
                {"handle": "playbook.version", "summary": "Required version marker for one playbook launch-catalog document rather than for one workflow file"},
                {"handle": "routine_contract.version", "summary": "Required version marker for the routine registry document"},
                {"handle": "workflow.workflow", "summary": "The top-level workflow identity field that the version marker makes safe to interpret"},
            ]},
            {"heading": "Examples", "examples": ["workflow.version with version: 0"]},
        ],
    }),
}


_CAPABILITY_TITLES: dict[str, str] = {
    "workflow.local_expressions": "Local expressions",
    "workflow.local_expression.adapter": "Representation adapters",
    "workflow.state_bindings": "State bindings",
    "workflow.state_needs": "State needs",
    "workflow.step.state_set": "State set step",
    "workflow.step.state_delete": "State delete step",
    "workflow.step.value": "Value step",
    "workflow.include_fragments": "Included fragments",
    "runtime.launchers": "Legacy launchers",
    "workflow.step.launcher": "Legacy launcher step",
    "workflow.step.condition": "Step conditions",
    "workflow.step.register": "Registered step output",
    "workflow.step.outputs": "Step outputs",
    "workflow.branching": "Workflow branching",
}


_NEGATIVE_RULE_TITLES: dict[str, str] = {
    "guard_expression.no_step_root": "Guards cannot read step output",
    "guard_expression.no_adapter_write_path": "Guard adapters are read-only",
    "guard_expression.boolean_result_required": "Guards need boolean decisions",
    "workflow_step.exactly_one_form": "Steps use one primary form",
    "workflow_step.with_requires_uses": "Use with only for invocations",
    "workflow_step.launcher_requires_uses": "Use launchers only for operation calls",
    "workflow_step.register_requires_uses": "Register only result-producing steps",
    "workflow_step.if_conflicts_with_register": "Optional steps cannot register results",
    "workflow_step.gate_conflicts_with_register": "Gated steps cannot register results",
    "embedded_value_expression.step_refs_must_be_backward": "Read results from earlier steps",
    "state_set.single_target_entry": "Write one state target per step",
    "workflow_fragment.no_state_surface": "Included fragments cannot access state",
    "workflow_state_role.write_after_last_read": "Write a state role after its last read",
    "workflow_state_storage.write_after_last_read": "Write storage after its final read",
    "workflow_state_storage.relevant_identity_required": "Establish storage identity before conflicting access",
    "format_value.args_must_be_list": "Formatting arguments are a list",
}


def capability_focused_describe_human(name: str) -> HumanDeclaration | None:
    """Return the focused reader-facing declaration for one capability handle."""

    return CAPABILITY_FOCUSED_DESCRIBE_HUMANS.get(name)


def capability_focused_describe_humans() -> tuple[HumanDeclaration, ...]:
    """Return every focused capability reader-facing declaration."""

    return tuple(CAPABILITY_FOCUSED_DESCRIBE_HUMANS.values())


def capabilities_human(contract: JSONObject) -> HumanDeclaration:
    """Reader-facing capability boundaries, kept with runtime capability data."""

    return declare_human({
        "title": "Capabilities",
        "goal": "Check whether a workflow surface is supported before relying on it.",
        "summary": "Use the boundary and restriction explanations before choosing an authoring shape.",
        "sections": [
            {"heading": "Workflow step forms", "items": [
                "Use `run` to invoke a named reusable target. For short local repeated work, pair `for_each` with inline `steps`; keep larger, reusable, or guarded repeated work behind `run`.",
                "Use `profile_switch` to select another declared profile for later work on the current path. Use `result` for one ordered result value and `publish` for a named caller-facing payload.",
                "Use `with` to pass explicit runtime values to a `uses` operation or `run` target. A run target reads its values as `args.name`; `include.with` instead binds source-time fragment arguments.",
                "An include binding is evaluated in the caller context and may read caller inputs, the current item, state, or an earlier registered step output. The expanded fragment receives only values declared as `args.name`.",
            ], "references": [
                {"handle": "workflow.step.run", "summary": "Invoke a named reusable target"},
                {"handle": "workflow.step.steps", "summary": "Define a short inline repeated body"},
                {"handle": "workflow.step.profile_switch", "summary": "Change the profile for later work"},
                {"handle": "workflow.step.result", "summary": "Append one ordered result value"},
                {"handle": "workflow.step.publish", "summary": "Publish a caller-facing payload"},
                {"handle": "workflow.step.with", "summary": "Pass operation or run-target values"},
            ]},
            {"heading": "Published surfaces", "subsections": [
                {"heading": item["human"]["title"], "body": item["human"]["summary"], "subsections": item["human"]["sections"]}
                for item in contract["capabilities"]
            ]},
            {"heading": "Restrictions", "subsections": [
                {"heading": item["human"]["title"], "body": item["human"]["summary"], "subsections": item["human"]["sections"]}
                for item in contract["negative_rules"]
            ]},
        ],
    })
