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
            "definition": "Minimal workflow example that composes one published operation into one small end-to-end workflow shape.",
            "shows": ["minimal_workflow", "public_operation_composition"],
            "related_topics": ["overview", "model", "operations"],
        },
        {
            "name": "inspect-issue",
            "path": "examples/inspect-issue.yaml",
            "definition": "Issue inspection example that uses a guard before loading one published GitHub issue probe.",
            "shows": ["guard_probe_usage", "blocked_before_execution"],
            "related_topics": ["capabilities", "model", "operations"],
        },
        {
            "name": "inspect-pr",
            "path": "examples/inspect-pr.yaml",
            "definition": "Pull-request inspection example that composes the published PR metadata, diff, comments, reviews, checks, and timeline surfaces into one summary.",
            "shows": ["pull_request_probe_composition", "orthogonal_pr_surfaces", "published_digest_inputs"],
            "related_topics": ["operations", "examples", "model"],
        },
        {
            "name": "set-active-task-from-gitx",
            "path": "examples/set-active-task-from-gitx.yaml",
            "definition": "Multi-step task-activation example that combines project updates, state writes, and legacy shell fallback steps in one workflow.",
            "shows": ["multi_step_workflow", "state_updates", "shell_fallback"],
            "related_topics": ["capabilities", "model", "operations"],
        },
        {
            "name": "launcher-step",
            "path": "examples/launcher-step.yaml",
            "definition": "Launcher selection example that shows one step-level launcher override inside a profile-scoped execution context.",
            "shows": ["step_launcher_selection", "profile_scoped_launchers", "shell_wrapper_example"],
            "related_topics": ["capabilities", "model", "examples"],
            "status": "legacy_compatibility_example",
        },
        {
            "name": "include-plain",
            "path": "examples/include-plain.yaml",
            "definition": "Workflow include example that reuses one plain fragment without passing include arguments.",
            "shows": ["workflow_include", "plain_fragment_reuse"],
            "related_topics": ["model", "examples"],
        },
        {
            "name": "include-args",
            "path": "examples/include-args.yaml",
            "definition": "Workflow include example that passes explicit arguments into one reusable fragment contract.",
            "shows": ["workflow_include", "fragment_args", "ordo_help_aligned_fragment_contract"],
            "related_topics": ["capabilities", "model", "examples"],
        },
        {
            "name": "playbook-workflows",
            "path": "examples/playbook-workflows.yaml",
            "definition": "Playbook workflow catalog example that shows one published workflow entry with defaults, profiles, and state bindings.",
            "shows": ["playbook_workflow_catalog", "workflow_entry_guidance", "entry_state_bindings"],
            "related_topics": ["features", "model", "examples"],
        },
        {
            "name": "playbook-pre-run",
            "path": "examples/playbook-pre-run.yaml",
            "definition": "Playbook pre-run example that inserts one shared preparation workflow before the requested published workflow runs.",
            "shows": ["playbook_pre_run", "runtime_profile_switch", "shared_preparation_stage"],
            "related_topics": ["model", "examples", "operations"],
        },
        {
            "name": "text-adapter",
            "path": "examples/text-adapter.yaml",
            "definition": "Text adapter example that projects, searches, and rewrites line-oriented text through the published text adapter surface.",
            "shows": ["text_adapter_line_projection", "text_adapter_literal_search", "text_adapter_bulk_mutation"],
            "related_topics": ["capabilities", "model", "examples"],
        },
        {
            "name": "local-expression-filters",
            "path": "examples/local-expression-filters.yaml",
            "definition": "Local-expression filter example that demonstrates type predicates, membership tests, and boolean flow over embedded values.",
            "shows": ["type_predicate_filters", "membership_filter", "embedded_value_boolean_flow"],
            "related_topics": ["model", "examples"],
        },
        {
            "name": "project-items-let",
            "path": "examples/project-items-let.yaml",
            "definition": "Project-items example that binds one collection probe through let and then filters it by field values.",
            "shows": ["project_collection_probe", "let_bound_probe_usage", "field_based_project_filtering"],
            "related_topics": ["operations", "examples", "model"],
        },
    ],
}


def describe_examples_catalog_data() -> JSONObject:
    """Return a defensive copy of the published example catalog."""

    return deepcopy(EXAMPLES_CATALOG)
