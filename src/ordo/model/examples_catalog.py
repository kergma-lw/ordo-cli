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
            "name": "set-active-task-from-gitx",
            "path": "examples/set-active-task-from-gitx.yaml",
            "shows": ["multi_step_workflow", "state_updates", "shell_fallback"],
            "related_topics": ["capabilities", "model", "operations"],
        },
        {
            "name": "launcher-step",
            "path": "examples/launcher-step.yaml",
            "shows": ["step_launcher_selection", "profile_scoped_launchers", "shell_wrapper_example"],
            "related_topics": ["capabilities", "model", "examples"],
        },
        {
            "name": "include-plain",
            "path": "examples/include-plain.yaml",
            "shows": ["workflow_include", "plain_fragment_reuse"],
            "related_topics": ["model", "examples"],
        },
        {
            "name": "include-args",
            "path": "examples/include-args.yaml",
            "shows": ["workflow_include", "fragment_args", "ordo_help_aligned_fragment_contract"],
            "related_topics": ["capabilities", "model", "examples"],
        },
        {
            "name": "playbook-pre-run",
            "path": "examples/playbook-pre-run.yaml",
            "shows": ["playbook_pre_run", "runtime_profile_switch", "shared_preparation_stage"],
            "related_topics": ["model", "examples", "operations"],
        },
        {
            "name": "text-adapter",
            "path": "examples/text-adapter.yaml",
            "shows": ["text_adapter_line_projection", "text_adapter_literal_search", "text_adapter_bulk_mutation"],
            "related_topics": ["capabilities", "model", "examples"],
        },
        {
            "name": "local-expression-filters",
            "path": "examples/local-expression-filters.yaml",
            "shows": ["type_predicate_filters", "membership_filter", "embedded_value_boolean_flow"],
            "related_topics": ["model", "examples"],
        },
    ],
}


def describe_examples_catalog_data() -> JSONObject:
    """Return a defensive copy of the published example catalog."""

    return deepcopy(EXAMPLES_CATALOG)
