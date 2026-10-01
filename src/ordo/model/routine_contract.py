"""Canonical contract metadata for project-local routine registries."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

from .json import JSONObject
from .human import HumanContent, HumanDeclaration, declare_human, human_mapping


ROUTINE_FEATURE_HUMAN = declare_human({
    "title": "Routines", "goal": "Use a small declared project-local helper only for a clear mechanical gap.",
    "summary": "A limited project-local helper path.", "sections": [],
})
ROUTINE_HUMAN = declare_human({
    "title": "Routine contract", "goal": "Publish a narrow project-local automation exception when structured workflow surfaces cannot express a mechanical need.",
    "summary": "Routines are a limited fallback, not the normal way to extend workflow authoring.",
    "sections": [
        {"heading": "Before using a routine", "items": ["Check whether one published operation or a composition already fits.", "Use a routine only for a bounded local mechanical task. Do not hide an unclear product or workflow decision in its helper.", "Keep the helper's command, accepted values, success result, and named failure outcomes reviewable in the project." ]},
        {"heading": "Declare the routine", "items": ["Create `.ordo/routines.yaml` with `version: 1` and a `routines` map. Each named routine requires `kind`, `summary`, `implementation`, and `failure_modes`.", "Add `args` only for values callers must supply. Add `outputs` when the workflow needs structured success data, and use `log_hints` only for optional operational guidance.", "`implementation.argv` is required. It is a fixed command and argument list, not shell text. A whole item such as `{target}` is replaced by the declared `target` value; a list value expands to separate arguments.", "Name every expected failure outcome in `failure_modes`, such as `check_failed` or `runtime_unavailable`, so a failed helper remains understandable to its caller." ]},
        {"heading": "Call it deliberately", "items": ["A workflow step uses `routine.<name>`. Put required call values under `with.args`; do not pass unspecified caller data.", "Use `with.env` only for a short explicit list of scalar references such as `inputs.profile`. Ordo does not copy all workflow inputs into the helper environment automatically and generates the environment-variable names."]},
        {"heading": "Complete author example", "items": ["Run `ordo-help describe routine_contract` to inspect the checked complete routine example. It declares `demo.echo`, its executable helper, the `{target}` placeholder, a named failure outcome, and a matching call. Start from that complete shape, then keep your helper equally small and local."], "references": [{"handle": "workflow-rules.routine.*", "summary": "Read the fallback boundary before adding a routine."}]},
        {"heading": "Replacing a legacy launcher", "items": ["When replacing an existing launcher-based step, first identify the launcher record through profile.launchers and the operation step through workflow.step.launcher. Then decide whether the remaining local automation belongs in a small declared helper."], "references": [{"handle": "profile.launchers", "summary": "Legacy launcher records to inspect during migration"}, {"handle": "workflow.step.launcher", "summary": "Legacy operation-step launcher selection"}, {"handle": "workflow-rules.routine.*", "summary": "Supported routine authoring path"}]},
    ],
    "feature_clusters": {"routines": {**human_mapping(ROUTINE_FEATURE_HUMAN), "use_when": ["Published operations are exhausted and the remaining gap is mechanical or project-local."], "avoid_when": ["The remaining gap is semantic or unclear."]}},
})


def _declare_focused_human(content: JSONObject) -> HumanDeclaration:
    """Declare focused-help content while retaining its source provenance."""

    return declare_human(cast(HumanContent, content))


ROUTINE_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "routine_contract.workflow_call_surface": _declare_focused_human({
        "definition": "Routine call settings for passing declared values and a short explicit list of scalar context references into one routine call.",
        "use_when": ["A workflow step calls routine.* and must distinguish its declared values from explicitly forwarded context."],
        "do_not_use_for": ["Broad implicit environment mirroring; routine calls forward context only through explicit env references.", "Treating routine call fields as ordinary workflow input declaration; this surface configures one routine invocation only."],
        "nearest_surfaces": [{"handle": "routine_contract.workflow_call.args", "summary": "Call field for declared routine business arguments"}, {"handle": "routine_contract.workflow_call.env", "summary": "Call field for explicit forwarded scalar context references"}, {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance for when routine.* is acceptable at all"}],
        "related_examples": [{"reference": "with.args", "inputs": {"target": "inputs.issue_number"}}, {"reference": "with.env", "inputs": {"refs": ["inputs.profile", "step.collect.outputs.value.path"]}}],
        "inspect_next": ["routine_contract.workflow_call.args", "routine_contract.workflow_call.env", "workflow-rules.routine.*"],
    }),
    "routine_contract.workflow_call.args": _declare_focused_human({
        "definition": "Routine call field for values that satisfy the routine's declared `args`.",
        "use_when": ["The routine declares `args` and the caller must supply concrete values to that call."],
        "do_not_use_for": ["Forwarding caller context such as inputs.* or step outputs; use workflow_call.env for those scalar references.", "Declaring what the routine accepts; that belongs to routine_contract.entry.args in the routine declaration."],
        "nearest_surfaces": [{"handle": "routine_contract.workflow_call_surface", "summary": "Parent routine call settings"}, {"handle": "routine_contract.workflow_call.env", "summary": "Sibling field for explicit forwarded scalar context references"}, {"handle": "routine_contract.entry.args", "summary": "Routine declaration of which call values it accepts"}],
        "related_examples": [{"reference": "with.args", "inputs": {"target": "inputs.issue_number"}}],
        "inspect_next": ["routine_contract.workflow_call.env", "routine_contract.entry.args", "routine_contract.workflow_call_surface"],
    }),
    "routine_contract.workflow_call.env": _declare_focused_human({
        "definition": "Routine workflow-call field for forwarding a short explicit list of scalar caller references as generated environment variables for the routine process.",
        "use_when": ["The routine truly needs ambient caller context and that context can be expressed as a short explicit list of scalar references."],
        "do_not_use_for": ["Call values that belong in with.args; env is for forwarded context references, not the main value being supplied.", "Objects, arrays, or custom environment-variable naming; non-scalar forwarding errors and env names are generated mechanically."],
        "nearest_surfaces": [{"handle": "routine_contract.workflow_call_surface", "summary": "Parent routine workflow-call surface"}, {"handle": "routine_contract.workflow_call.args", "summary": "Sibling field for declared business arguments"}, {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that limits routine env forwarding to short explicit scalar lists"}],
        "related_examples": [{"reference": "with.env", "inputs": {"refs": ["inputs.profile", "step.collect.outputs.value.path"]}}],
        "inspect_next": ["routine_contract.workflow_call.args", "workflow-rules.routine.*", "routine_contract.workflow_call_surface"],
    }),
    "routine_contract.entry.args": _declare_focused_human({
        "definition": "Routine declaration field for listing the values a routine accepts from workflow_call.args.",
        "use_when": ["A routine needs an explicit list of accepted values instead of silently consuming arbitrary caller data."],
        "do_not_use_for": ["Forwarded context references; those belong to workflow_call.env.", "Encoding the command that runs the helper; accepted values are separate from implementation."],
        "nearest_surfaces": [{"handle": "routine_contract.workflow_call.args", "summary": "Call field that supplies the declared values"}, {"handle": "routine_contract.entry.implementation", "summary": "Sibling routine declaration field for the helper command"}, {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that limits routines to a narrow exception"}],
        "related_examples": [{"reference": "entry.args", "inputs": {"target": {"type": "string", "required": True}}}],
        "inspect_next": ["routine_contract.workflow_call.args", "routine_contract.entry.implementation", "workflow-rules.routine.*"],
    }),
    "routine_contract.entry.implementation": _declare_focused_human({
        "definition": "Routine declaration field for the command that runs the project-local helper.",
        "use_when": ["A routine must state exactly how its small project-local helper runs instead of relying on unstated conventions."],
        "do_not_use_for": ["Accepted values or named failure outcomes; those belong to sibling routine fields.", "General free-form shell authoring; this field accepts only a command argument list."],
        "nearest_surfaces": [{"handle": "routine_contract.implementation.argv", "summary": "Required command argument list"}, {"handle": "routine_contract.entry.args", "summary": "Sibling field that declares accepted call values"}, {"handle": "routine_contract.entry.failure_modes", "summary": "Sibling field that declares expected failure outcomes"}],
        "related_examples": [{"reference": "entry.implementation", "inputs": {"argv": [".ordo/scripts/demo-check", "{target}"]}}],
        "inspect_next": ["routine_contract.implementation.argv", "routine_contract.entry.failure_modes", "routine_contract.entry.args"],
    }),
    "routine_contract.implementation.argv": _declare_focused_human({
        "definition": "Routine implementation field for the command argument list that launches the local helper.",
        "use_when": ["The routine must state the exact command vector that runs the helper process."],
        "do_not_use_for": ["Inline shell-language authoring or broad command synthesis; argv is an explicit argument vector, not a generic script body.", "Routine business-argument declaration; argv consumes already-declared args rather than defining them."],
        "effects": ["For example, `argv: [.ordo/scripts/demo-check, \"{target}\"]` starts that helper with the declared `target` argument. A whole argv item written as `{argument_name}` is replaced with the call's matching declared argument; a list value supplies separate argv items."],
        "nearest_surfaces": [{"handle": "routine_contract.entry.implementation", "summary": "Parent implementation field that requires argv"}, {"handle": "routine_contract.entry.args", "summary": "Routine declaration of values that argv placeholders may consume"}, {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that keeps routine execution limited and exceptional"}],
        "related_examples": [{"reference": "implementation.argv", "inputs": {"argv": [".ordo/scripts/demo-check", "{target}"]}}],
        "inspect_next": ["routine_contract.entry.implementation", "routine_contract.entry.args", "workflow-rules.routine.*"],
    }),
    "routine_contract.entry.failure_modes": _declare_focused_human({
        "definition": "Routine declaration field for naming the expected failure outcomes that this project-local helper may report.",
        "use_when": ["A routine should expose reviewable failure semantics instead of collapsing every implementation problem into one opaque generic failure."],
        "do_not_use_for": ["Ad hoc debug notes or implementation detail dumps; failure_modes should stay as named outward-facing outcomes.", "Skipping failure declaration because the helper might fail unpredictably; the fallback is less reviewable without explicit outcomes."],
        "nearest_surfaces": [{"handle": "routine_contract.entry.implementation", "summary": "Sibling field that defines the helper command whose failures are being classified"}, {"handle": "routine_contract.entry.outputs", "summary": "Sibling outward contract field for successful routine result shape"}, {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that treats routines as narrow, reviewable exception surfaces"}],
        "related_examples": [{"reference": "entry.failure_modes", "inputs": {"failure_modes": ["check_failed", "helper_failed"]}}],
        "inspect_next": ["routine_contract.entry.outputs", "routine_contract.entry.implementation", "workflow-rules.routine.*"],
    }),
    "routine_contract.entry.kind": _declare_focused_human({
        "definition": "Routine declaration field for the required kind marker of this limited fallback.",
        "use_when": ["A routine needs its required kind marker so the declaration records which limited fallback shape it represents."],
        "do_not_use_for": ["The purpose or behavior readers need to understand; those belong to summary, args, outputs, and failure_modes.", "Treating kind as a substitute for a richer published operation; routines remain an exception path."],
        "nearest_surfaces": [{"handle": "routine_contract.entry.summary", "summary": "Sibling field for the short human-facing purpose of the routine entry"}, {"handle": "routine_contract.entry.implementation", "summary": "Sibling field for the declared command that actually runs the helper"}, {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that keeps routine publication narrow and exceptional"}],
        "inspect_next": ["routine_contract.entry.summary", "routine_contract.entry.implementation", "workflow-rules.routine.*"],
    }),
    "routine_contract.entry.summary": _declare_focused_human({
        "definition": "Routine declaration field for the short purpose statement that explains what the helper does.",
        "use_when": ["A routine needs a concise reviewable explanation of its limited project-local helper role."],
        "do_not_use_for": ["Full behavior or execution details; summary should stay short and pair with args, implementation, outputs, and failure_modes.", "Replacing explicit output or failure declarations with prose alone."],
        "nearest_surfaces": [{"handle": "routine_contract.entry.kind", "summary": "Sibling field for the routine entry classification"}, {"handle": "routine_contract.entry.outputs", "summary": "Sibling field for declared successful result shape"}, {"handle": "routine_contract.entry.failure_modes", "summary": "Sibling field for declared outward-facing failure classes"}],
        "inspect_next": ["routine_contract.entry.outputs", "routine_contract.entry.failure_modes", "routine_contract.entry.kind"],
    }),
    "routine_contract.entry.outputs": _declare_focused_human({
        "definition": "Routine declaration field for describing the successful result a routine may return to the workflow.",
        "use_when": ["A routine returns structured success data and that outward contract should be reviewable instead of remaining implicit in helper behavior."],
        "do_not_use_for": ["Execution logs or debug-only helper chatter; outputs are the successful result contract, not generic process output.", "Failure classification; use failure_modes for named outward-facing failure classes."],
        "nearest_surfaces": [{"handle": "routine_contract.entry.failure_modes", "summary": "Sibling field for declared outward-facing failure classes"}, {"handle": "routine_contract.entry.summary", "summary": "Sibling short purpose statement for the routine entry"}, {"handle": "routine_contract.workflow_call_surface", "summary": "Call surface that feeds args and env into a routine that may later return declared outputs"}],
        "inspect_next": ["routine_contract.entry.failure_modes", "routine_contract.workflow_call_surface", "routine_contract.entry.summary"],
    }),
    "routine_contract.entry.log_hints": _declare_focused_human({
        "definition": "Routine declaration field for optional logging hints that help explain helper execution without changing what the routine does.",
        "use_when": ["A routine benefits from lightweight operator-facing log guidance beyond its summary and failure/output contracts."],
        "do_not_use_for": ["Business outputs or failure classes; log_hints should not become a second implicit contract surface.", "Replacing the required implementation or failure declaration with commentary alone."],
        "nearest_surfaces": [{"handle": "routine_contract.entry.summary", "summary": "Sibling field for the short human-facing purpose statement"}, {"handle": "routine_contract.entry.outputs", "summary": "Sibling field for declared successful outward result shape"}, {"handle": "routine_contract.entry.failure_modes", "summary": "Sibling field for declared failure classes"}],
        "inspect_next": ["routine_contract.entry.summary", "routine_contract.entry.outputs", "routine_contract.entry.failure_modes"],
    }),
    "routine_contract.routines": _declare_focused_human({
        "definition": "Top-level field that contains this project's named routine declarations.",
        "use_when": ["The routine file needs one map of names that workflows may reference through routine.*."],
        "do_not_use_for": ["A catalog of general extensions; routines stay a limited project-local exception surface."],
        "nearest_surfaces": [{"handle": "routine_contract.version", "summary": "Sibling top-level field for the routine registry schema version"}, {"handle": "routine_contract.entry.summary", "summary": "Representative entry field inside the named routines map"}, {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that treats the whole registry as an exception path"}],
        "inspect_next": ["routine_contract.version", "routine_contract.entry.summary", "workflow-rules.routine.*"],
    }),
    "routine_contract.version": _declare_focused_human({
        "definition": "Top-level field for the format version of the project-local routine file.",
        "use_when": ["The routine file needs an explicit version so Ordo can validate its expected shape."],
        "do_not_use_for": ["Routine helper release numbering or data versioning; this field versions the routine file format itself."],
        "nearest_surfaces": [{"handle": "routine_contract.routines", "summary": "Sibling top-level field that contains the named routine entry map"}, {"handle": "routine_contract", "summary": "Top-level routine contract surface for the project-local registry"}, {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance for when the routine registry should exist at all"}],
        "inspect_next": ["routine_contract.routines", "routine_contract.entry.summary", "workflow-rules.routine.*"],
    }),
}

ROUTINE_ADDITIONAL_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "routine_contract": _declare_focused_human({
        "title": "Routine contract",
        "goal": "Use a limited project-local helper only after published workflow surfaces do not fit a mechanical need.",
        "summary": "A routine declares a narrow, reviewable local automation boundary rather than a general extension mechanism.",
        "sections": [
            {"heading": "Contract detail", "items": ["The published routine format is available as `routine_contract` for tools that need machine-readable details.", "Run `ordo-help describe routine_contract` to inspect the checked complete routine example." ]},
            {"heading": "Boundary", "items": ["Do not hide an unclear product or workflow decision inside a routine."]},
        ],
    }),
}

ROUTINE_CONTRACT: JSONObject = {
    "document_kind": "routine_registry",
    "version": 1,
    "discovery": {"path": ".ordo/routines.yaml"},
    "authoring_status": "exception_path",
    "authoring_guidance": {
        "default_recommendation": "avoid_by_default",
        "role": "bounded_project_local_opaque_automation",
        "not_a_connector_family": True,
        "use_when": "no richer public surface exists and the remaining gap is mechanical or intentionally project-local",
        "avoid_when": "the remaining gap is semantic or a reusable connector model should exist instead",
    },
    "workflow_call_surface": {
        "fields": [
            {"name": "args", "required": False, "type": "object", "role": "declared_business_arguments"},
            {"name": "env", "required": False, "type": "list[string]", "role": "explicit_forwarded_scalar_context_references"},
        ],
        "automatic_input_env_projection": False,
        "env_reference_roots": ["inputs", "step", "state"],
        "env_reference_pattern": "supported_reference_path_only",
        "generated_env_name_prefix": "ORDO_",
        "generated_env_name_examples": {
            "inputs.profile": "ORDO_INPUTS_PROFILE",
            "step.collect.outputs.value.path": "ORDO_STEP_COLLECT_OUTPUTS_VALUE_PATH",
        },
        "env_scalar_only": True,
        "env_non_scalar_behavior": "execution_error",
    },
    "top_level_fields": [
        {"name": "version", "required": True, "type": "integer"},
        {"name": "routines", "required": True, "type": "object"},
    ],
    "routine_entry_fields": [
        {"name": "kind", "required": True, "type": "string", "authoring_status": "exception_path"},
        {"name": "summary", "required": True, "type": "string"},
        {"name": "args", "required": False, "type": "object"},
        {"name": "implementation", "required": True, "type": "object"},
        {"name": "failure_modes", "required": True, "type": "array"},
        {"name": "outputs", "required": False, "type": "object"},
        {"name": "log_hints", "required": False, "type": "object"},
    ],
    "implementation_fields": [
        {"name": "argv", "required": True, "type": "array", "authoring_status": "bounded_execution_only"},
    ],
    "human": human_mapping(ROUTINE_HUMAN),
}


def describe_routine_contract_data() -> JSONObject:
    """Return a defensive copy of canonical routine-registry contract metadata."""

    return deepcopy(ROUTINE_CONTRACT)


def routine_focused_describe_human(handle: str) -> HumanDeclaration | None:
    """Return the canonical focused-describe content for one routine handle."""

    return (ROUTINE_FOCUSED_DESCRIBE_HUMAN | ROUTINE_ADDITIONAL_FOCUSED_DESCRIBE_HUMAN).get(handle)
