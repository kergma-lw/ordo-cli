"""Canonical cross-domain navigation for the basic help route."""

from __future__ import annotations

from .human import HumanDeclaration, declare_human, human_mapping
from .json import JSONObject


def _keyword(name: str, *targets: tuple[str, str, str | None]) -> dict[str, object]:
    """Declare one human keyword with its intended focused-help destinations."""

    return {
        "name": name,
        "targets": [
            {
                "handle": handle,
                "summary": summary,
                **({"keyword": keyword} if keyword is not None else {}),
            }
            for handle, summary, keyword in targets
        ],
    }


_ADAPTER_FOCUSED_HANDLES = {
    "json": ("workflow.local_expression.adapter.json", "Read the JSON adapter family."),
    "key_value": ("workflow.local_expression.adapter.key_value", "Read the key-value adapter family."),
    "markdown": ("workflow.local_expression.adapter.markdown", "Read the Markdown adapter family."),
    "text": ("workflow.local_expression.adapter.text", "Read the plain-text adapter family."),
    "yaml": ("workflow.local_expression.adapter.yaml", "Read the YAML adapter family."),
}

_ADAPTER_KEYWORD_TERMS = {
    "json": ("field", "one", "many", "set", "remove"),
    "markdown": (
        "prelude", "blocks", "add", "append", "replace", "remove", "list", "lists",
        "list_items", "task_list", "task_lists", "task_list_items", "paragraph", "paragraphs",
    ),
    "text": ("lines", "find", "finds", "before", "after", "append", "replace", "remove"),
    "yaml": ("field", "one", "many"),
}


def _adapter_keywords() -> list[dict[str, object]]:
    """Declare normalized adapter vocabulary without publishing syntax samples as names."""

    entries = [_keyword(name, (*target, None)) for name, target in _ADAPTER_FOCUSED_HANDLES.items()]
    targets_by_term: dict[str, list[tuple[str, str]]] = {}
    for family, terms in _ADAPTER_KEYWORD_TERMS.items():
        target = _ADAPTER_FOCUSED_HANDLES[family]
        for term in terms:
            entries.append(_keyword(
                f"{family}.{term}",
                (target[0], f"Use `{term}` with the {family.replace('_', '-')} adapter.", f"{family}.{term}"),
            ))
            targets_by_term.setdefault(term, []).append(target)
    for term in targets_by_term:
        targets = []
        for family, terms in _ADAPTER_KEYWORD_TERMS.items():
            if term in terms:
                handle, summary = _ADAPTER_FOCUSED_HANDLES[family]
                targets.append((handle, summary, f"{family}.{term}"))
        entries.append(_keyword(term, *targets))
    return entries


ROOT_HUMAN = declare_human({
    "title": "Ordo help",
    "goal": "Find the public authoring surface that matches the work you need to do.",
    "summary": "Start with features for authoring choices or overview for navigation.",
    "sections": [
        {"heading": "Recommended first calls", "references": [
            {"handle": "features", "summary": "Choose an authoring surface before introducing a fallback."},
            {"handle": "overview", "summary": "Navigate the main public help topics."},
            {"handle": "model", "summary": "Read the project and workflow contracts."},
            {"handle": "workflow-rules", "summary": "Review preferred authoring practices."},
            {"handle": "capabilities", "summary": "Check support boundaries."},
        ]},
        {"heading": "Open a focused guide", "items": [
            "When a page names a handle such as `playbook.workflows` or `workflow.step.profile_switch`, run `ordo-help describe <handle>` to read its focused guide.",
            "Use `ordo-help search <words>` when you know the goal but not the handle; search results include the exact focused-help command.",
        ]},
    ],
})

OVERVIEW_HUMAN = declare_human({
    "title": "Overview",
    "goal": "Find the next public help surface without learning implementation details first.",
    "summary": "Use the feature map for authoring choices, then inspect the owning contract or rule.",
    "sections": [
        {"heading": "Author workflows", "references": [
            {"handle": "features", "summary": "Map a task to an existing authoring surface."},
            {"handle": "model", "summary": "Read workflow, playbook, profile, state, and routine contracts."},
            {"handle": "workflow-rules", "summary": "Apply the preferred workflow design rules."},
            {"handle": "capabilities", "summary": "Confirm supported and restricted surfaces."},
        ]},
        {"heading": "Choose control surfaces", "items": [
            "Use guards to decide whether a workflow applies and to reject it early.",
            "Use gates to decide whether an already-valid path may run.",
            "Use if only for optional local behavior inside an already-valid path.",
        ]},
        {"heading": "Validate changes", "items": [
            "Run check to see whether the workflow applies and is ready to execute.",
            "Run review to find workflow-quality issues that readiness alone does not answer.",
            "Treat check and review as complementary passes after every workflow change.",
        ]},
        {"heading": "Run and inspect", "references": [
            {"handle": "command-line", "summary": "Use the public command-line entrypoints."},
            {"handle": "operations", "summary": "Browse published connector operations."},
            {"handle": "examples", "summary": "Inspect verified repository examples."},
        ]},
    ],
})

MODEL_HUMAN = declare_human({
    "title": "Workflow model",
    "goal": "Understand which domain owns each part of a workflow-enabled project.",
    "summary": "Each linked contract owns its reader-facing explanation and its machine-readable declaration.",
    "sections": [
        {"heading": "Open a focused guide", "references": [
            {"handle": "workflow.workflow", "summary": "Name a workflow before defining its inputs, guards, steps, and outputs."},
            {"handle": "playbook.workflows", "summary": "Publish a project's workflow catalog and activation context."},
            {"handle": "profile.name", "summary": "Name a project's execution context."},
            {"handle": "state", "summary": "Coordinate durable handoff between workflow stages."},
            {"handle": "routine_contract", "summary": "Use a narrow local-automation fallback only when justified."},
        ]},
    ],
})

FEATURES_HUMAN = declare_human({
    "title": "Workflow-authoring feature map",
    "goal": "Choose the narrowest published authoring surface that expresses the intended workflow behavior.",
    "summary": "Use the clusters to choose a surface, then follow their published handles for details.",
    "keywords": [
        *_adapter_keywords(),
        _keyword("if", ("workflow.step.if", "Read local optional workflow behavior.", None)),
    ],
    "sections": [
        {"heading": "Read a named surface", "items": [
            "Each handle in this map has a focused guide: run `ordo-help describe <handle>` after choosing a surface.",
            "Choose include for source-level fragment reuse, run for a later fragment invocation or bounded repeated work, and profile switch when later work needs another declared profile.",
            "Use playbook workflows to publish named workflows with shared defaults or pre-run preparation before the requested workflow starts.",
            "Profiles can publish input defaults, explicit overrides, and legacy launchers; overrides are metadata, while launchers are compatibility-only setup for older workflows.",
        ]},
    ],
})

SEARCH_HUMAN = declare_human({
    "title": "Search help",
    "goal": "Find a public help topic, operation, or reader-facing reference by words you know.",
    "summary": "Exact public keywords appear before broader matches. Search matches only published reader-facing help, not hidden contract details.",
    "sections": [
        {"heading": "Use search", "items": [
            "Run ordo-help search followed by the words you want to find.",
            "When the words exactly name a public keyword, use the first result's focused-help command.",
            "Add `--all` to an exact keyword search when you also want its broader matches.",
            "Open a returned command for the full reader-facing guide.",
        ]},
    ],
})

FOCUSED_DESCRIBE_HUMAN = declare_human({
    "title": "Focused help",
    "goal": "Read the guide for one public reference.",
    "summary": "Focused help uses the reference's own reader-facing guide when one is published.",
    "sections": [],
})


def keyword_dispatcher_human(keyword: str, references: list[JSONObject]) -> HumanDeclaration:
    """Declare reader-facing guidance for one ambiguous public keyword."""

    return declare_human({
        "title": keyword,
        "goal": "Choose the public guide whose adapter family matches the value you are working with.",
        "summary": f"`{keyword}` is available in more than one published adapter family.",
        "sections": [{"heading": "Choose a focused guide", "references": references}],
    })  # type: ignore[arg-type]


def model_human(contracts: list[JSONObject]) -> HumanDeclaration:
    """Join domain-owned contract explanations without exposing contract shapes."""

    content = dict(human_mapping(MODEL_HUMAN))
    content.update({
        "summary": "Each section is a domain-owned explanation; use focused help for exact declarations.",
        "sections": [*human_mapping(MODEL_HUMAN)["sections"],
            {"heading": "Contracts", "subsections": [
                {
                    "heading": contract["human"]["title"],
                    "body": contract["human"]["summary"],
                    "subsections": contract["human"]["sections"],
                }
                for contract in contracts
            ]},
        ],
    })
    return declare_human(content)  # type: ignore[arg-type]


FEATURE_CLUSTER_ORDER = (
    "playbook", "profile", "workflow", "state", "include", "run", "guards", "gates",
    "conditions", "local-expressions", "connectors", "routines", "adapters",
)


def features_human(clusters: list[JSONObject], cluster_human: dict[str, JSONObject]) -> HumanDeclaration:
    """Return the cross-domain feature navigation projection."""

    content = dict(human_mapping(FEATURES_HUMAN))
    keywords = list(content["keywords"])
    content.update({
        "sections": [*human_mapping(FEATURES_HUMAN)["sections"],
            {"heading": "Feature clusters", "subsections": [
                _feature_cluster_human(
                    next(cluster for cluster in clusters if cluster["name"] == name),
                    cluster_human[name],
                    keywords,
                )
                for name in FEATURE_CLUSTER_ORDER
            ]},
            {"heading": "Decision boundary", "items": ["Use a direct published surface first.", "Compose published surfaces when they fit cleanly.", "Treat a remaining semantic gap as a reason to clarify, not a reason to improvise a fallback."]},
        ],
    })
    return declare_human(content)  # type: ignore[arg-type]


def _feature_cluster_human(
    cluster: JSONObject, content: JSONObject, keywords: list[object],
) -> JSONObject:
    """Project one domain cluster as a compact navigation entry."""

    if cluster["name"] == "adapters":
        public_names = _adapter_public_names(keywords)
    else:
        public_names = _published_names(cluster)
    return {
        "heading": str(cluster["name"]).replace("-", " ").title(),
        "body": str(content["summary"]),
        "subsections": [
            {"heading": "Public names", "items": public_names},
        ],
    }


def _published_names(cluster: JSONObject) -> list[str]:
    """Render compact public names for a cluster that has not moved to the keyword catalogue."""

    public_names: list[str] = []
    for category, values in cluster.get("published_names", {}).items():
        if category in {"runtime_rules", "generated_env_name_examples"}:
            continue
        if isinstance(values, list) and values:
            public_names.append(f"{str(category).replace('_', ' ')}: {', '.join(map(str, values))}")
        elif isinstance(values, dict):
            for name, names in values.items():
                if isinstance(names, list) and names:
                    public_names.append(f"{str(name).replace('_', ' ')}: {', '.join(map(str, names))}")
    return public_names


def _adapter_public_names(keywords: list[object]) -> list[str]:
    """Render adapter names from the canonical keyword catalogue, never from syntax samples."""

    families = list(_ADAPTER_FOCUSED_HANDLES)
    grouped: dict[str, list[str]] = {family: [] for family in families}
    for keyword in keywords:
        if not isinstance(keyword, dict) or not isinstance(keyword.get("name"), str):
            continue
        name = keyword["name"]
        if "." not in name:
            continue
        family, term = name.split(".", 1)
        if family in grouped:
            grouped[family].append(term)
    lines = [f"families: {', '.join(families)}"]
    lines.extend(f"{family}: {', '.join(sorted(terms))}" for family, terms in grouped.items() if terms)
    return lines
