"""Canonical contract metadata for project-local routine registries."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

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
}


def describe_routine_contract_data() -> JSONObject:
    """Return a defensive copy of canonical routine-registry contract metadata."""

    return deepcopy(ROUTINE_CONTRACT)
