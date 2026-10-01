"""Canonical contract metadata for runtime state surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject
from .human import HumanDeclaration, declare_human, human_mapping


STATE_FEATURE_HUMAN = declare_human({
    "title": "State", "goal": "Choose durable state only for handoff between related workflow runs.",
    "summary": "Durable coordination data shared by related workflow stages.", "sections": [],
})
STATE_HUMAN = declare_human({
    "title": "State contract", "goal": "Coordinate related workflow stages with a small amount of durable project state.",
    "summary": "Use state only for durable handoff between workflows, not ordinary workflow-local dataflow.",
    "sections": [{"heading": "Keep state safe", "items": ["Bind state locations in the playbook.", "Keep stored values small and durable.", "Use step registers for data needed only during one workflow run."]}, {"heading": "Related guidance", "references": [{"handle": "workflow-rules", "summary": "Follow the lifecycle-state rule when deciding whether data belongs in state."}]}],
    "feature_clusters": {"state": {**human_mapping(STATE_FEATURE_HUMAN), "use_when": ["A small value must survive across workflow runs."], "avoid_when": ["The data is local to one workflow run."]}},
})

# Focused-describe records live with the state contract so their guidance has
# the same source of truth as the fields it explains.
STATE_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "state": declare_human({
        "definition": "Store a small named value for a later related workflow run.",
        "use_when": [
            "A workflow needs a remembered value. Declare its role in state_needs before reading or changing it.",
            "Bind each declared role to a named state location in the playbook before the workflow uses it.",
            "Read state through state.<role>[<key>]. Put every state_set or state_delete after the final read of that value.",
        ],
        "do_not_use_for": [
            "Passing newly computed values between steps in one run; use value + register and step.<register>.outputs.value instead.",
        ],
        "related_surfaces": [
            {"handle": "workflow.state_needs", "summary": "Declare the state roles a workflow needs"},
            {"handle": "workflow.state_bindings", "summary": "Bind workflow roles to playbook state locations"},
            {"handle": "workflow.step.state_set", "summary": "Write a value to bound state"},
            {"handle": "workflow.step.state_delete", "summary": "Remove a value from bound state"},
        ],
    }),
    "state.workflow_surface.step_state_delete_field": declare_human({
        "definition": "State workflow-surface field that marks `state_delete` as the explicit step-owned durable deletion surface inside workflow authoring.",
        "use_when": ["You need the contract meaning of the state_delete step field rather than only an example of removing state."],
        "do_not_use_for": ["Assuming durable state can be removed implicitly without the workflow's surrounding state-binding contract."],
        "nearest_surfaces": [{"handle": "workflow.step.state_delete", "summary": "Step capability for deleting one explicit bound state target"}, {"handle": "workflow.step_forms.state_delete", "summary": "Named step form that requires state_delete as its primary field"}, {"handle": "workflow.step.state_set", "summary": "Sibling durable state mutation capability for explicit writes instead of deletion"}],
        "inspect_next": ["workflow.step.state_delete", "workflow.step_forms.state_delete", "workflow.step.state_set"],
    }),
    "state.workflow_surface.state_needs_field": declare_human({
        "definition": "State workflow-surface field that marks `state_needs` as the top-level workflow contract surface for declaring durable state requirements before binding and mutation surfaces are used.",
        "use_when": ["You need the contract meaning of the workflow's state_needs declaration rather than only one example of a later bound state operation."],
        "do_not_use_for": ["Assuming a later state_set, state_delete, or state read implicitly declares workflow state requirements on its own."],
        "nearest_surfaces": [{"handle": "workflow.state_needs", "summary": "Workflow capability for declaring durable state requirements before binding and mutation"}, {"handle": "workflow.state_bindings", "summary": "Capability for binding declared playbook state locations into workflow roles after state_needs exists"}, {"handle": "playbook.states", "summary": "Playbook surface that declares the named durable state locations a workflow may later bind"}],
        "inspect_next": ["workflow.state_needs", "workflow.state_bindings", "playbook.states"],
    }),
    "state.workflow_surface.state_binding_field": declare_human({
        "definition": "State workflow-surface field that marks `state_bindings` as the workflow contract surface for connecting declared workflow state roles to named playbook state locations.",
        "use_when": ["You need the contract meaning of the workflow's state_bindings declaration rather than only one later step that reads or changes state."],
        "do_not_use_for": ["Declaring state requirements in the abstract; that earlier declaration belongs to state_needs.", "Inventing undeclared playbook state locations on the fly; bindings connect to already-declared playbook state names."],
        "nearest_surfaces": [{"handle": "workflow.state_bindings", "summary": "Workflow capability for binding state roles to declared playbook locations"}, {"handle": "workflow.state_needs", "summary": "Earlier workflow declaration of which state roles are needed before binding"}, {"handle": "playbook.states", "summary": "Playbook catalog that declares the named durable state locations a binding may target"}],
        "inspect_next": ["workflow.state_bindings", "workflow.state_needs", "playbook.states"],
    }),
    "state.workflow_surface.step_state_set_field": declare_human({
        "definition": "State workflow-surface field that marks `state_set` as the explicit step-owned durable write surface inside workflow authoring.",
        "use_when": ["You need the contract meaning of the state_set step field rather than just one example of writing state."],
        "do_not_use_for": ["Assuming any state path write is valid without the surrounding workflow state-binding contract and single-target rule."],
        "nearest_surfaces": [{"handle": "workflow.step.state_set", "summary": "Step capability for writing one explicit value into one bound state target"}, {"handle": "workflow.step_forms.state_set", "summary": "Named step form that requires state_set as its primary field"}, {"handle": "state_set.single_target_entry", "summary": "Negative rule that forbids more than one target entry in a state_set step"}],
        "inspect_next": ["workflow.step.state_set", "workflow.step_forms.state_set", "state_set.single_target_entry"],
    }),
}

STATE_ADDITIONAL_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "state.workflow_surface.storage_targets_field": declare_human({
        "title": "State storage locations",
        "goal": "Declare named durable locations before workflows bind and use shared state.",
        "summary": "Use named storage locations to keep durable workflow handoff explicit and reviewable.",
        "sections": [
            {"heading": "Contract detail", "items": ["The published playbook storage field is `states`." ]},
            {"heading": "Boundary", "items": ["Do not create an undeclared storage location from a step or a profile."]},
        ],
    }),
    "state_set.single_target_entry": declare_human({
        "title": "Single state target",
        "goal": "Make each durable state write identify one clear target.",
        "summary": "Use one state target per write step so ordering, review, and failure reporting remain unambiguous.",
        "sections": [
            {"heading": "Contract detail", "items": ["The published write form is `state_set` with one target entry."]},
            {"heading": "Boundary", "items": ["Split independent writes into separate steps instead of combining them in one state mutation."]},
        ],
    }),
}

STATE_CONTRACT: JSONObject = {
    "document_kind": "state_contract",
    "workflow_surface": {
        "state_needs_field": "state_needs",
        "state_binding_field": "state_bindings",
        "storage_targets_field": "states",
        "step_state_set_field": "state_set",
        "step_state_delete_field": "state_delete",
    },
    "path_forms": {
        "root": "state",
        "shape": "state.<role>[<expression>][.<field>...]",
        "key_expression_surface": "embedded_value_expression",
        "supports_nested_fields": True,
        "supports_hyphenated_roles": True,
    },
    "invalid_path_rules": [
        {
            "name": "root_must_be_state",
            "message": "state path must start with 'state'",
        },
        {
            "name": "key_expression_must_be_valid_local_expression",
            "message": "state path key expression must be a valid local expression",
        },
        {
            "name": "no_trailing_content",
            "message": "state path must not contain trailing content",
        },
    ],
    "storage_document": {
        "root_type": "object",
        "top_level_keys": "user-defined",
    },
    "preflight": {
        "classification": "effectful",
        "top_level_status": "deferred",
        "rule": "Check conditions and gates first, then defer eligible top-level mutations without mutation, simulation, outputs, registers, or reusable observations; continue to independent guards.",
        "planning": "Retain ordered nodes with reuse_policy not_reusable and planned_probe_result null; execute admitted mutations once in order, with divergence_status not_applicable for deferred nodes.",
        "boundary": "Nested analysis does not defer mutations. A reached run or loop after deferral halts with state_deferral_invocation_barrier; profile switches cannot resume that barrier.",
        "verification_scope": "Validate individual workflows and children, not flattened caller-child access streams. Cross-invocation and cross-iteration guarantees remain deferred; this is not a full composed-run or cross-run proof.",
    },
    "runtime_rules": [
        {
            "name": "write_after_last_read",
            "message": "Before binding, authoring validation requires writes or deletes of a logical state role only after its final read, regardless of key or field. Bound validation instead compares actual storage in each access context. Use step registers for per-run dataflow.",
            "error_code": "validation.workflow.state_role.write_before_last_read",
        },
        {
            "name": "bound_storage_write_after_last_read",
            "message": "After binding, write or delete only after the final read of the same actual file, regardless of role, state name, profile, key, or field. Resolve relative paths in each access context; normalized paths, symlinks, and existing hardlinks can alias. The same role may access different files and be valid.",
            "error_code": "validation.workflow.state_storage.write_before_last_read",
        },
        {
            "name": "relevant_storage_identity_required",
            "message": "Conservatively reject early only relevant write/later-read pairs whose storage identity cannot be established without execution or observations. This is not a proven ordering violation; uncertain context alone does not reject read-only, read-before-write, or known-disjoint access. Cross-invocation and cross-iteration guarantees remain deferred, without a new loop mutation ban.",
            "error_code": "validation.workflow.state_storage.identity_unresolved",
        },
        {
            "name": "bound_role_required",
            "message": "state role must be bound before runtime access",
            "error_code": "runtime.state.binding_missing",
        },
        {
            "name": "non_null_scalar_key_required",
            "message": "state key expression must resolve to a non-null scalar value",
            "error_code": "runtime.state.key_invalid",
        },
        {
            "name": "declared_location_required",
            "message": "undeclared state locations are runtime errors",
            "error_code": "runtime.state.declaration_missing",
        },
    ],
    "human": human_mapping(STATE_HUMAN),
}


def describe_state_contract_data() -> JSONObject:
    """Return a defensive copy of canonical state contract metadata."""

    return deepcopy(STATE_CONTRACT)


def describe_state_focused_describe_human() -> dict[str, JSONObject]:
    """Return defensive copies of state-focused describe records."""

    return {name: deepcopy(declaration.content) for name, declaration in STATE_FOCUSED_DESCRIBE_HUMAN.items()}  # type: ignore[return-value]
