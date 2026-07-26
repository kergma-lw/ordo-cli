"""Machine-readable self-description contract for plugin and external connector surfaces."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

PLUGIN_SURFACE_CONTRACT: JSONObject = {
    "document_kind": "plugin_surface_contract",
    "connector_requirements": {
        "required_fields": ["namespace", "bootstrap", "operations"],
        "shared_registry": "public_connector_registry",
    },
    "bootstrap_requirements": {
        "required_fields": ["prerequisites", "context_fields"],
        "optional_fields": [],
    },
    "operation_requirements": {
        "required_fields": [
            "name",
            "kind",
            "summary",
            "inputs",
            "prerequisites",
            "effects",
            "outputs",
            "failure_modes",
            "tags",
            "examples",
            "maturity",
            "deprecated",
            "replaced_by",
            "invalidates_observations",
            "preflight_observations",
        ],
        "kind_values": ["probe", "action"],
    },
    "participation_rules": {
        "shared_introspection_sections": ["operations"],
        "special_case_help_logic_required": False,
        "publication_model": "plugin metadata must enter introspection through the same public connector registry contract as built-in families",
    },
}


def describe_plugin_surface_contract_data() -> JSONObject:
    """Return a defensive copy of the plugin surface contract."""

    return deepcopy(PLUGIN_SURFACE_CONTRACT)
