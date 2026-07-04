"""Canonical contract metadata for profile authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

PROFILE_CONTRACT: JSONObject = {
    "document_kind": "profile",
    "top_level_fields": [
        {"name": "name", "required": True, "type": "string"},
        {"name": "inputs", "required": False, "type": "object"},
        {"name": "checks", "required": False, "type": "array"},
        {"name": "overrides", "required": False, "type": "array"},
    ],
    "override_fields": [
        {"name": "target", "required": True, "type": "string"},
        {"name": "with", "required": False, "type": "object"},
        {"name": "reason", "required": False, "type": "string"},
    ],
    "compose_semantics": {
        "inputs": "first-writer wins; conflicting later values are validation errors",
        "checks": "deduplicated left-to-right union",
        "overrides": "duplicate override targets across profiles are validation errors",
    },
    "workflow_apply_semantics": {
        "inputs": "profile may add missing workflow inputs but may not override explicit workflow input values",
        "checks": "profile checks do not mutate workflow contract",
        "overrides": "profile overrides remain explicit metadata and do not silently mutate workflow steps",
    },
}


def describe_profile_contract_data() -> JSONObject:
    """Return a defensive copy of canonical profile contract metadata."""

    return deepcopy(PROFILE_CONTRACT)
