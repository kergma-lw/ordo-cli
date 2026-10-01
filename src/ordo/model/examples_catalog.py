"""Published verified example descriptors for discovery surfaces."""

from __future__ import annotations

from copy import deepcopy

from .human import HumanDeclaration, declare_human, human_mapping
from .json import JSONObject


EXAMPLES_HUMAN = declare_human({
    "title": "Verified examples",
    "goal": "Find a working repository example to inspect before authoring a similar workflow.",
    "summary": "Each entry names a verified example file and the workflow behavior it demonstrates.",
    "sections": [
        {"heading": "How to use these examples", "items": [
            "Repository examples are complete files verified in this repository and linked from the generated site.",
            "A snippet-backed example is a smaller excerpt checked for a focused `ordo-help describe` guide. It can explain one surface but does not replace a complete repository example.",
        ]},
        {"heading": "Compatibility example", "items": [
            "The launcher-step example is retained for compatibility with older workflows. For new work, prefer routines or explicit profile context; run `ordo-help describe examples.launcher-step` for the migration-aware guide.",
        ]},
    ],
})


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
            "definition": "Native task-activation sequence that checks project policy, updates status, fetches and fast-forwards the base, selects a task branch, and remembers task state, with an optional explicit trusted-code hook.",
            "shows": ["project_policy_gates", "native_git_sequence", "state_updates", "explicit_trusted_hook", "partial_effects"],
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
            "name": "playbook-connectors",
            "path": "examples/playbook-connectors.yaml",
            "definition": "Playbook top-level example that shows the required version marker together with repository-wide connector defaults before workflow and profile activation.",
            "shows": ["playbook_version_marker", "playbook_connector_defaults", "profile_override_boundary"],
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
            "name": "run-fan-out",
            "path": "examples/run-fan-out.yaml",
            "definition": "Run-invocation example that contrasts named run-target fan-out with inline repeated steps, including outer if, gate, with, and register fields.",
            "shows": ["run_target_invocation", "bounded_fan_out", "inline_repeated_steps"],
            "related_topics": ["model", "examples", "workflow-rules"],
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
            "name": "let-bindings",
            "path": "examples/let-bindings.yaml",
            "definition": "Workflow-local named expressions reuse input defaults in a boolean guard and publish a lowercased branch label as data, without running a shell command or creating a Git branch.",
            "shows": ["let_bindings", "boolean_guard", "publish_data"],
            "related_topics": ["features", "model", "examples"],
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


def _example_focused_human(
    *, title: str, summary: str, path: str, demonstrates: list[str], related_topics: list[str],
    status: str | None = None, related_surfaces: list[JSONObject] | None = None,
) -> HumanDeclaration:
    """Declare reader-facing focused help beside one example's catalog data."""

    sections: list[JSONObject] = [
        {"heading": "Example file", "items": [path]},
        {"heading": "What it demonstrates", "items": demonstrates},
        {"heading": "Related topics", "items": related_topics},
    ]
    if status is not None:
        sections.append({"heading": "Status", "items": [status]})
    if related_surfaces is not None:
        sections.append({"heading": "Related guidance", "references": related_surfaces})
    return declare_human({
        "title": title,
        "goal": "Inspect this verified example before authoring a similar workflow.",
        "summary": summary,
        "sections": sections,
    })  # type: ignore[arg-type]


EXAMPLE_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "minimal": _example_focused_human(
        title="minimal",
        summary="Minimal workflow example that composes one published operation into one small end-to-end workflow shape.",
        path="examples/minimal.yaml",
        demonstrates=["A minimal workflow", "Composing a published operation"],
        related_topics=["overview", "model", "operations"],
    ),
    "inspect-issue": _example_focused_human(
        title="inspect-issue",
        summary="Issue inspection example that uses a guard before loading one published GitHub issue probe.",
        path="examples/inspect-issue.yaml",
        demonstrates=["Using a guard probe", "Stopping before execution when a guard does not pass"],
        related_topics=["capabilities", "model", "operations"],
    ),
    "inspect-pr": _example_focused_human(
        title="inspect-pr",
        summary="Pull-request inspection example that composes the published PR metadata, diff, comments, reviews, checks, and timeline surfaces into one summary.",
        path="examples/inspect-pr.yaml",
        demonstrates=["Composing pull-request inspection operations", "Separate pull-request information surfaces", "Inputs to a published digest"],
        related_topics=["operations", "examples", "model"],
    ),
    "set-active-task-from-gitx": _example_focused_human(
        title="set-active-task-from-gitx",
        summary="Native task-activation sequence that checks project policy, updates status, fetches and fast-forwards the base, selects a task branch, and remembers task state, with an optional explicit trusted-code hook.",
        path="examples/set-active-task-from-gitx.yaml",
        demonstrates=["Project-policy gates", "Native Git sequence", "Remembering task state", "An explicit trusted-code hook", "Partial effects on failure"],
        related_topics=["capabilities", "model", "operations"],
    ),
    "launcher-step": _example_focused_human(
        title="launcher-step",
        summary="Launcher selection example that shows one step-level launcher override inside a profile-scoped execution context.",
        path="examples/launcher-step.yaml",
        demonstrates=["Selecting a launcher for one step", "Profile-scoped launchers", "A shell-wrapper example"],
        related_topics=["capabilities", "model", "examples"],
        status="Legacy compatibility example. Keep it only when maintaining older launcher-based workflows; prefer routines or explicit profile context for new work.",
        related_surfaces=[
            {"handle": "profile.launchers", "summary": "Read the deprecated profile launcher boundary and its preferred replacement."},
            {"handle": "workflow.step.launcher", "summary": "Understand the older step field that consumes a launcher."},
            {"handle": "workflow-rules.routine.*", "summary": "Choose the preferred limited project-local helper path."},
        ],
    ),
    "include-plain": _example_focused_human(
        title="include-plain",
        summary="Workflow include example that reuses one plain fragment without passing include arguments.",
        path="examples/include-plain.yaml",
        demonstrates=["Including a workflow fragment", "Reusing a fragment without arguments"],
        related_topics=["model", "examples"],
    ),
    "include-args": _example_focused_human(
        title="include-args",
        summary="Workflow include example that passes explicit arguments into one reusable fragment contract.",
        path="examples/include-args.yaml",
        demonstrates=["Including a workflow fragment", "Fragment arguments", "An Ordo-help-aligned fragment contract"],
        related_topics=["capabilities", "model", "examples"],
    ),
    "playbook-workflows": _example_focused_human(
        title="playbook-workflows",
        summary="Playbook workflow catalog example that shows one published workflow entry with defaults, profiles, and state bindings.",
        path="examples/playbook-workflows.yaml",
        demonstrates=["A playbook workflow catalog", "Guidance for a workflow entry", "Workflow-entry state bindings"],
        related_topics=["features", "model", "examples"],
    ),
    "playbook-connectors": _example_focused_human(
        title="playbook-connectors",
        summary="Playbook top-level example that shows the required version marker together with repository-wide connector defaults before workflow and profile activation.",
        path="examples/playbook-connectors.yaml",
        demonstrates=["A playbook version marker", "Playbook connector defaults", "Profile override boundaries"],
        related_topics=["features", "model", "examples"],
    ),
    "playbook-pre-run": _example_focused_human(
        title="playbook-pre-run",
        summary="Playbook pre-run example that inserts one shared preparation workflow before the requested published workflow runs.",
        path="examples/playbook-pre-run.yaml",
        demonstrates=["A playbook pre-run workflow", "Switching the runtime profile", "A shared preparation stage"],
        related_topics=["model", "examples", "operations"],
    ),
    "run-fan-out": _example_focused_human(
        title="run-fan-out",
        summary="Run-invocation example that contrasts named run-target fan-out with inline repeated steps, including outer if, gate, with, and register fields.",
        path="examples/run-fan-out.yaml",
        demonstrates=["Calling a named run target", "Bounded fan-out", "Inline repeated steps"],
        related_topics=["model", "examples", "workflow-rules"],
    ),
    "text-adapter": _example_focused_human(
        title="text-adapter",
        summary="Text adapter example that projects, searches, and rewrites line-oriented text through the published text adapter surface.",
        path="examples/text-adapter.yaml",
        demonstrates=["Projecting lines of text", "Literal text search", "Bulk text changes"],
        related_topics=["capabilities", "model", "examples"],
    ),
    "local-expression-filters": _example_focused_human(
        title="local-expression-filters",
        summary="Local-expression filter example that demonstrates type predicates, membership tests, and boolean flow over embedded values.",
        path="examples/local-expression-filters.yaml",
        demonstrates=["Type checks", "Membership checks", "Boolean flow over embedded values"],
        related_topics=["model", "examples"],
    ),
    "let-bindings": _example_focused_human(
        title="let-bindings",
        summary="Workflow-local named expressions reuse input defaults in a boolean guard and publish a lowercased branch label as data, without running a shell command or creating a Git branch.",
        path="examples/let-bindings.yaml",
        demonstrates=["Let bindings", "A boolean guard", "Publishing data"],
        related_topics=["features", "model", "examples"],
    ),
    "project-items-let": _example_focused_human(
        title="project-items-let",
        summary="Project-items example that binds one collection probe through let and then filters it by field values.",
        path="examples/project-items-let.yaml",
        demonstrates=["A project collection probe", "Using a probe result through let", "Filtering project items by field values"],
        related_topics=["operations", "examples", "model"],
    ),
}


def example_focused_describe_human(name: str) -> HumanDeclaration | None:
    """Return the canonical focused-help declaration for one public example."""

    return EXAMPLE_FOCUSED_DESCRIBE_HUMAN.get(name)


def public_example_names() -> tuple[str, ...]:
    """Return the public example names supported by focused help."""

    return tuple(EXAMPLE_FOCUSED_DESCRIBE_HUMAN)


def examples_catalog_human(examples: list[JSONObject]) -> HumanDeclaration:
    """Return the reader-facing example catalog beside its semantic source."""

    content = dict(human_mapping(EXAMPLES_HUMAN))
    content["sections"] = [*content["sections"], {
        "heading": "Examples",
        "items": [
            f"{example['name']}: {example['definition']} See {example['path']}."
            for example in examples
        ],
    }]
    return declare_human(content)  # type: ignore[arg-type]


def describe_examples_catalog_data() -> JSONObject:
    """Return a defensive copy of the published example catalog."""

    return deepcopy(EXAMPLES_CATALOG)
