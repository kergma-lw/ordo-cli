"""Published verified example descriptors for discovery surfaces."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject


EXAMPLES_CATALOG: JSONObject = {
    "document_kind": "examples_catalog",
    "examples": [
        {
            "name": "minimal",
            "path": "examples/minimal.yaml",
            "shows": ["minimal_workflow", "public_operation_composition"],
            "related_topics": ["overview", "model", "operations"],
        },
        {
            "name": "inspect-issue",
            "path": "examples/inspect-issue.yaml",
            "shows": ["guard_probe_usage", "blocked_before_execution"],
            "related_topics": ["capabilities", "model", "operations"],
        },
        {
            "name": "open-task-from-gitx",
            "path": "examples/open-task-from-gitx.yaml",
            "shows": ["multi_step_workflow", "state_updates", "shell_fallback"],
            "related_topics": ["capabilities", "model", "operations"],
        },
        {
            "name": "launcher-step",
            "path": "examples/launcher-step.yaml",
            "shows": ["step_launcher_selection", "profile_scoped_launchers", "shell_wrapper_example"],
            "related_topics": ["capabilities", "model", "examples"],
        },
    ],
}


def describe_examples_catalog_data() -> JSONObject:
    """Return a defensive copy of the published example catalog."""

    return deepcopy(EXAMPLES_CATALOG)
