"""Machine-readable guidance hints kept separate from canonical contracts."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

PATTERN_HINTS: JSONObject = {
    "document_kind": "pattern_hints",
    "hints": [
        {
            "name": "profiles.prefer_for_environment_differences",
            "category": "authoring_strategy",
            "when": "A workflow needs backend/frontend or environment-specific defaults without changing its core step graph",
            "prefer": ["profile_contract"],
            "because": "Profiles separate environment-specific inputs and checks from the canonical workflow shape",
        },
        {
            "name": "state.use_for_persistent_memory",
            "category": "authoring_strategy",
            "when": "A workflow needs persistent memory across runs keyed by workflow inputs",
            "prefer": ["workflow_contract.state_needs", "state_contract", "workflow_step.state_set"],
            "because": "State bindings plus state_set/state_delete provide the runtime-owned persistent memory surface",
        },
        {
            "name": "shell_command.use_as_capability_fallback",
            "category": "fallback_strategy",
            "when": "A needed runtime action is not published as a dedicated connector capability",
            "prefer": ["shell.command"],
            "because": "shell.command is the explicit low-level fallback when no higher-level connector operation exists",
        },
    ],
}


def describe_pattern_hints_data() -> JSONObject:
    """Return a defensive copy of the published pattern hints."""

    return deepcopy(PATTERN_HINTS)
