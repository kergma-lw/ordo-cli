#!/usr/bin/env python3
"""Generate a more readable GitHub Pages-friendly Markdown site from ordo-help."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ORDO_HELP = ROOT / "ordo-help"
DEFAULT_OUTPUT = ROOT / "site-docs"
STATIC_TOPICS = (
    "overview",
    "model",
    "workflow-authoring",
    "capabilities",
    "command-line",
    "operations",
    "examples",
)

TOPIC_TITLES = {
    "overview": "Overview",
    "model": "Authoring model",
    "workflow-authoring": "Workflow authoring",
    "capabilities": "Capabilities",
    "command-line": "Command-line reference",
    "operations": "Operation catalog",
    "examples": "Examples",
}

TOPIC_INTROS = {
    "overview": "Start here for a map of the main Ordo surfaces.",
    "model": "This page outlines the main authoring contracts used in workflows, playbooks, profiles, and runtime state.",
    "workflow-authoring": "Use this page when adding, changing, or reviewing workflows.",
    "capabilities": "This page shows what Ordo supports, restricts, or deprecates.",
    "command-line": "This page summarizes the public CLI surface and the main execution modes.",
    "operations": "This page lists public operations by connector namespace.",
    "examples": "This page collects verified examples you can inspect as reference material.",
}

TOPIC_SUMMARY_REWRITES = {
    "Start with the Ordo world map": "Start with a map of the main Ordo surfaces.",
    "Inspect the main authoring contracts": "Browse the main authoring contracts.",
    "Inspect preferred workflow authoring patterns, paired check/review passes, routine cautions, early guards, and let usage": "Browse workflow authoring guidance, from the default check/review loop to fallback cautions.",
    "Inspect supported and unsupported surfaces": "See which surfaces are supported, restricted, or deprecated.",
    "Inspect the public command-line launch surface, including distinct check and review roles": "See the public CLI surface and how check, review, plan, and run differ.",
    "Inspect the public connector catalog": "Browse the public connector operations.",
    "Inspect verified repository examples": "Browse verified workflow examples from the repository.",
}

TOPIC_USE_WHEN = {
    "overview": "Use this page first when you need to understand where to look next.",
    "model": "Use this page when you need field-level contract details for authoring work.",
    "workflow-authoring": "Use this page when you are deciding how to structure or review a workflow.",
    "capabilities": "Use this page when you need to know whether a surface is supported, restricted, or deprecated.",
    "command-line": "Use this page when you need the public CLI entrypoints, flags, and execution modes.",
    "operations": "Use this page when you need to find a concrete operation that a workflow can call.",
    "examples": "Use this page when you want concrete repository examples to inspect side by side with the reference docs.",
}

NAMESPACE_GLOSS = {
    "runtime": "Runtime compatibility and execution-context operations.",
    "git": "Operations for reading and changing local Git state.",
    "gh": "Operations for reading and changing GitHub state.",
    "shell": "Low-level shell execution surface.",
}

KNOWN_OPERATION_SUMMARIES = {
    "git.branch": "Read the current Git branch.",
    "git.branches": "List local Git branches.",
    "git.branch.create": "Create a new local Git branch.",
    "git.branch.delete": "Delete a local Git branch.",
    "git.branch.switch": "Switch the current checkout to a local Git branch.",
    "git.commit.amend": "Amend the current Git commit.",
    "git.commit.create": "Create a new Git commit from the current index.",
    "git.commit.revert": "Create a Git commit that reverts another commit.",
    "git.commits": "Read a bounded list of Git commits.",
    "git.index.add_all": "Stage all current worktree changes.",
    "git.integrate.cherry_pick": "Cherry-pick a Git commit onto the current checkout.",
    "git.integrate.merge": "Merge a Git ref into the current checkout.",
    "git.integrate.merge_ff_only": "Fast-forward merge a Git ref into the current checkout.",
    "git.integrate.rebase_onto": "Rebase a Git branch range onto a new base.",
    "git.range": "Compare two Git refs and report ahead/behind counts.",
    "git.ref": "Read metadata for a Git ref.",
    "git.repo": "Read Git repository metadata.",
    "git.stash": "List Git stash entries.",
    "git.state": "Read the current Git working-state summary.",
    "git.sync.fetch": "Fetch Git refs from a remote.",
    "git.sync.push": "Push a local Git branch to a remote.",
    "git.upstream": "Read upstream tracking information for the current branch.",
    "git.worktree": "Read the current Git worktree state.",
    "git.worktrees": "List Git worktrees.",
    "gh.issue": "Read a GitHub issue.",
    "gh.issue.body.append": "Append text to a GitHub issue body.",
    "gh.issue.body.replace": "Replace a GitHub issue body.",
    "gh.issue.close": "Close a GitHub issue.",
    "gh.issue.comment.add": "Add a comment to a GitHub issue.",
    "gh.issue.comments": "Read comments from a GitHub issue.",
    "gh.issue.create": "Create a GitHub issue.",
    "gh.project": "Read a GitHub Project.",
    "gh.project.field": "Read metadata for a GitHub Project field.",
    "gh.project.field.option": "Check whether a GitHub Project field exposes a named option.",
    "gh.project.issue": "Read one issue's membership and field values in a GitHub Project.",
    "gh.project.issue.add": "Add a GitHub issue to a GitHub Project.",
    "gh.project.issue.field_iteration.set": "Set an iteration field for a GitHub Project issue.",
    "gh.project.issue.field_number.set": "Set a number field for a GitHub Project issue.",
    "gh.project.issue.field_single_select.set": "Set a single-select field for a GitHub Project issue.",
    "gh.project.items": "Read normalized items from a GitHub Project.",
    "runtime.profile.use": "Switch the runtime execution profile for later work in the current run.",
    "shell.command": "Run a shell command.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Markdown documentation from ordo-help JSON surfaces.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory for generated Markdown files (default: %(default)s)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep existing output directory contents instead of rebuilding from scratch.",
    )
    return parser.parse_args()


def run_help(*args: str) -> dict[str, Any]:
    result = subprocess.run(
        [str(ORDO_HELP), *args, "--json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def slug(value: str) -> str:
    return value.replace(".", "-").replace("_", "-")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n```"


def bullet_list(items: list[str], empty: str = "- None") -> list[str]:
    if not items:
        return [empty]
    return [f"- {item}" for item in items]


def operation_doc_path(reference: str) -> Path:
    namespace, name = reference.split(".", 1)
    return Path("operations") / namespace / f"{slug(name)}.md"


def topic_doc_path(topic: str) -> Path:
    return Path("topics") / f"{topic}.md"


def rel_link(from_path: Path, to_path: Path) -> str:
    return Path(os.path.relpath(to_path, from_path.parent)).as_posix()


def doc_link(label: str, from_path: Path, to_path: Path, summary: str | None = None) -> str:
    suffix = f" — {summary}" if summary else ""
    return f"- [{label}]({rel_link(from_path, to_path)}){suffix}"


def topic_title(topic: str) -> str:
    return TOPIC_TITLES.get(topic, topic.replace("-", " ").title())


def topic_intro(topic: str, doc: dict[str, Any]) -> str:
    return TOPIC_INTROS.get(topic, doc.get("purpose", ""))


def topic_use_when(topic: str) -> str:
    return TOPIC_USE_WHEN.get(topic, "Use this page when you need reference details for this topic.")


def humanize_topic_summary(summary: str) -> str:
    return TOPIC_SUMMARY_REWRITES.get(summary, summary)


def namespace_gloss(namespace: str) -> str:
    return NAMESPACE_GLOSS.get(namespace, f"Operations in the `{namespace}` namespace.")


def lower_first(text: str) -> str:
    if not text:
        return text
    return text[0].lower() + text[1:]


def title_from_operation_name(name: str) -> str:
    return name.replace("_", " ").replace(".", " ")


def fallback_operation_summary(reference: str, op: dict[str, Any]) -> str:
    _, name = reference.split(".", 1)
    kind = op.get("kind", "")
    title = title_from_operation_name(name)
    if kind == "probe":
        if name.endswith("s"):
            return f"Inspect {title}."
        return f"Read {title}."
    if kind == "action":
        return f"Run {title}."
    return op.get("summary", reference)


def humanize_operation_summary(reference: str, op: dict[str, Any]) -> str:
    summary = op.get("summary", "")
    if reference in KNOWN_OPERATION_SUMMARIES:
        return KNOWN_OPERATION_SUMMARIES[reference]
    if summary.startswith("Probe operation '") or summary.startswith("Action operation '"):
        return fallback_operation_summary(reference, op)
    return summary or fallback_operation_summary(reference, op)


def humanize_operation_use_when(reference: str, op: dict[str, Any]) -> str:
    namespace, _ = reference.split(".", 1)
    summary = lower_first(humanize_operation_summary(reference, op).rstrip("."))
    if namespace == "git":
        return f"Use this when a workflow needs Git state or Git side effects. In practice: {summary}."
    if namespace == "gh":
        return f"Use this when a workflow needs to inspect or change GitHub state. In practice: {summary}."
    if namespace == "runtime":
        return f"Use this for runtime-level compatibility or execution-context work. In practice: {summary}."
    if namespace == "shell":
        return f"Use this only when a low-level shell surface is truly required. In practice: {summary}."
    return f"Use this when a workflow needs this exact operation surface. In practice: {summary}."


def render_topic_header(topic: str, doc: dict[str, Any]) -> list[str]:
    lines = [
        f"# {topic_title(topic)}",
        "",
        topic_intro(topic, doc),
        "",
        topic_use_when(topic),
        "",
    ]
    if doc.get("purpose") and doc.get("purpose") != topic_intro(topic, doc):
        lines += [f"**CLI purpose:** {doc['purpose']}", ""]
    return lines


def render_root_index(root_doc: dict[str, Any], topics: list[str], operation_refs: list[str]) -> str:
    page = Path("index.md")
    lines = [
        "# Ordo help reference",
        "",
        "Generated reference pages from `./ordo-help --json`.",
        "",
        "This site is meant to be browsed as product reference rather than as a narrative tutorial.",
        "",
        "## Start here",
        "",
    ]
    topic_summaries = {topic["name"]: topic.get("summary", "") for topic in root_doc.get("topics", [])}
    for topic in topics:
        lines.append(
            doc_link(
                topic_title(topic),
                page,
                topic_doc_path(topic),
                humanize_topic_summary(topic_summaries.get(topic, "")),
            )
        )
    lines += [
        "",
        "## Navigation commands",
        "",
        "These are interactive discovery surfaces in `ordo-help`, so they are listed here as commands rather than static pages.",
        "",
    ]
    for topic in root_doc.get("topics", []):
        if topic["name"] not in topics:
            lines.append(f"- `{topic['name']}` — {humanize_topic_summary(topic.get('summary', ''))}")
    lines += [
        "",
        "## Recommended first calls",
        "",
    ]
    for item in root_doc.get("recommended_first_calls", []):
        lines.append(f"- `{item['command']}` — {item['purpose']}")
    lines += [
        "",
        "## Operation reference",
        "",
        doc_link("All operations", page, Path("operations/index.md"), f"{len(operation_refs)} published operations"),
        "",
        "## Full JSON reference",
        "",
        json_block(root_doc),
    ]
    return "\n".join(lines)


def render_overview(page: Path, doc: dict[str, Any]) -> str:
    lines = render_topic_header("overview", doc)
    lines += [
        "## Published topics",
        "",
    ]
    lines.extend(bullet_list([f"`{name}`" for name in doc.get("published_topics", [])]))
    lines += [
        "",
        "## Connector namespaces",
        "",
    ]
    for name in doc.get("connector_namespaces", []):
        lines.append(f"- `{name}` — {namespace_gloss(name)}")
    lines += [
        "",
        "## Execution concepts",
        "",
        "### Modes",
        "",
    ]
    lines.extend(bullet_list([f"`{name}`" for name in doc.get("execution_concepts", {}).get("modes", [])]))
    lines += [
        "",
        "### Statuses",
        "",
    ]
    lines.extend(bullet_list([f"`{name}`" for name in doc.get("execution_concepts", {}).get("statuses", [])]))
    lines += [
        "",
        "## Workflow authoring loop",
        "",
        doc.get("workflow_authoring_passes", {}).get("rule", ""),
        "",
    ]
    for item in doc.get("workflow_authoring_passes", {}).get("passes", []):
        lines.append(f"- `{item['command']}` — {item['purpose']}")
    lines += [
        "",
        "## Recommended next calls",
        "",
    ]
    for item in doc.get("recommended_next_calls", []):
        lines.append(f"- `{item['command']}` — {item['purpose']}")
    lines += ["", "## Full JSON reference", "", json_block(doc)]
    return "\n".join(lines)


def render_model(doc: dict[str, Any]) -> str:
    lines = render_topic_header("model", doc)
    if doc.get("document_kinds"):
        lines += ["## Published document kinds", ""]
        lines.extend(bullet_list([f"`{kind}`" for kind in doc.get("document_kinds", [])]))
        lines.append("")
    lines += ["## Full JSON reference", "", json_block(doc)]
    return "\n".join(lines)


def render_command_line(doc: dict[str, Any]) -> str:
    lines = render_topic_header("command-line", doc)
    for command in doc.get("commands", []):
        lines += [
            f"## {command['name']}",
            "",
            command.get("purpose", ""),
            "",
            f"**Usage:** `{command.get('usage', '')}`",
            "",
            "### Modes",
            "",
        ]
        for mode in command.get("modes", []):
            lines.append(f"- `{mode['name']}` — {mode['summary']}")
        lines += ["", "### Flags", ""]
        for flag in command.get("flags", []):
            value_shape = f" (`{flag['value_shape']}`)" if flag.get("value_shape") else ""
            lines.append(f"- `{flag['name']}`{value_shape} — {flag['summary']}")
        lines += ["", "### Discovery commands", ""]
        for item in command.get("discovery_commands", []):
            lines.append(f"- `{item['name']}` — {item['summary']}")
        lines += ["", "### Input override precedence", ""]
        lines.extend(bullet_list(command.get("input_override_precedence", [])))
        authoring = command.get("authoring_passes", {})
        if authoring:
            lines += ["", "### Workflow authoring loop", "", authoring.get("rule", ""), ""]
            for item in authoring.get("passes", []):
                lines.append(f"- `{item['mode']}` — {item['purpose']} _Question: {item['question']}_")
        lines += ["", "### Example commands", ""]
        lines.extend(bullet_list([f"`{example}`" for example in command.get("examples", [])]))
        lines.append("")
    lines += ["## Full JSON reference", "", json_block(doc)]
    return "\n".join(lines)


def render_examples(page: Path, doc: dict[str, Any]) -> str:
    lines = render_topic_header("examples", doc)
    for example in doc.get("examples", []):
        lines += [f"## {example['name']}", "", f"- Path: `{example['path']}`"]
        if example.get("status"):
            lines.append(f"- Status: `{example['status']}`")
        lines.append(f"- Verified: `{str(example.get('verified', False)).lower()}`")
        if example.get("shows"):
            lines.append(f"- Highlights: {', '.join(f'`{item}`' for item in example['shows'])}")
        if example.get("related_topics"):
            related = []
            for topic in example["related_topics"]:
                target = topic_doc_path(topic)
                related.append(f"[{topic_title(topic)}]({rel_link(page, target)})")
            lines.append(f"- Related topics: {', '.join(related)}")
        lines.append("")
    lines += ["## Full JSON reference", "", json_block(doc)]
    return "\n".join(lines)


def render_operations_topic(page: Path, doc: dict[str, Any]) -> str:
    lines = render_topic_header("operations", doc)
    for connector in doc.get("connectors", []):
        namespace = connector["namespace"]
        lines += [f"## {namespace}", "", namespace_gloss(namespace), ""]
        bootstrap = connector.get("bootstrap", {})
        lines += ["### Requirements", ""]
        lines.extend(bullet_list(bootstrap.get("prerequisites", [])))
        lines += ["", "### Available context", ""]
        lines.extend(bullet_list([f"`{field}`" for field in bootstrap.get("context_fields", [])]))
        lines += ["", "### Operations", ""]
        for operation in connector.get("operations", []):
            reference = f"{namespace}.{operation['name']}"
            lines.append(
                doc_link(reference, page, operation_doc_path(reference), humanize_operation_summary(reference, operation))
            )
        lines.append("")
    lines += ["## Full JSON reference", "", json_block(doc)]
    return "\n".join(lines)


def render_operation(page: Path, doc: dict[str, Any]) -> str:
    reference = doc["reference"]
    op = doc["operation"]
    lines = [
        f"# {reference}",
        "",
        humanize_operation_summary(reference, op),
        "",
        humanize_operation_use_when(reference, op),
        "",
        f"- Namespace: `{doc['namespace']}`",
        f"- Kind: `{op.get('kind', '')}`",
        f"- Maturity: `{op.get('maturity', '')}`",
        f"- Deprecated: `{str(op.get('deprecated', False)).lower()}`",
        "",
    ]
    if doc.get("related_commands"):
        lines += ["## Related commands", ""]
        for label, command in doc["related_commands"].items():
            lines.append(f"- `{label}` — `{command}`")
        lines.append("")
    lines += ["## Inputs", "", json_block(op.get("inputs", {})), "", "## Outputs", "", json_block(op.get("outputs", {})), ""]
    lines += ["## Effects", ""]
    lines.extend(bullet_list(op.get("effects", [])))
    lines += ["", "## Failure modes", ""]
    lines.extend(bullet_list([f"`{name}`" for name in op.get("failure_modes", [])]))
    lines += ["", "## Requirements", ""]
    lines.extend(bullet_list(op.get("prerequisites", [])))
    if op.get("preflight_observations"):
        lines += ["", "## Preflight observations", "", json_block(op["preflight_observations"])]
    if op.get("invalidates_observations"):
        lines += ["", "## Invalidated observations", ""]
        lines.extend(bullet_list([f"`{item}`" for item in op.get("invalidates_observations", [])]))
    if op.get("examples"):
        lines += ["", "## Example inputs", ""]
        for example in op["examples"]:
            lines.append(f"### `{example.get('reference', '')}`")
            lines.append("")
            lines.append(json_block(example.get("inputs", {})))
            lines.append("")
    lines += ["## Full JSON reference", "", json_block(doc)]
    return "\n".join(lines)


def render_capabilities(doc: dict[str, Any]) -> str:
    lines = render_topic_header("capabilities", doc)
    lines += ["## Capabilities", ""]
    for capability in doc.get("capabilities", []):
        lines.append(f"### {capability['name']}")
        lines.append("")
        lines.append(f"- Scope: `{capability.get('scope', '')}`")
        lines.append(f"- Status: `{capability.get('status', '')}`")
        if capability.get("related_capabilities"):
            lines.append("- Related capabilities: " + ", ".join(f"`{item}`" for item in capability["related_capabilities"]))
        if capability.get("related_model_nodes"):
            lines.append("- Related model nodes: " + ", ".join(f"`{item}`" for item in capability["related_model_nodes"]))
        if capability.get("related_negative_rules"):
            lines.append("- Related negative rules: " + ", ".join(f"`{item}`" for item in capability["related_negative_rules"]))
        if capability.get("must_not_infer"):
            lines.append("- Do not infer:")
            lines.extend(f"  - {item}" for item in capability["must_not_infer"])
        lines.append("")
    lines += ["## Negative rules", ""]
    for rule in doc.get("negative_rules", []):
        lines += [
            f"### {rule['name']}",
            "",
            f"- Surface: `{rule.get('surface', '')}`",
            f"- Rule: {rule.get('rule', '')}",
            f"- Reason: {rule.get('reason', '')}",
        ]
        if rule.get("related_codes"):
            lines.append("- Related codes: " + ", ".join(f"`{item}`" for item in rule["related_codes"]))
        lines.append("")
    lines += ["## Expression surfaces", "", json_block(doc.get("expression_surfaces", [])), "", "## Full JSON reference", "", json_block(doc)]
    return "\n".join(lines)


def render_workflow_authoring(doc: dict[str, Any]) -> str:
    lines = render_topic_header("workflow-authoring", doc)
    heuristic = doc.get("authoring_heuristic", [])
    if heuristic:
        lines += ["## Default authoring loop", ""]
        lines.extend(bullet_list(heuristic))
        lines.append("")
    for rule in doc.get("rules", doc.get("workflow_authoring_rules", [])):
        lines += [
            f"## {rule['name']}",
            "",
            f"- Priority: `{rule.get('priority', '')}`",
            f"- Guidance level: `{rule.get('guidance_level', '')}`",
            f"- Rule: {rule.get('rule', '')}",
            "",
            "### Why this exists",
            "",
        ]
        lines.extend(bullet_list(rule.get("why", [])))
        lines += ["", "### Prefer", ""]
        lines.extend(bullet_list(rule.get("prefer", [])))
        lines += ["", "### Avoid", ""]
        lines.extend(bullet_list(rule.get("avoid", [])))
        if rule.get("must_not_infer"):
            lines += ["", "### Do not infer", ""]
            lines.extend(bullet_list(rule.get("must_not_infer", [])))
        if rule.get("stop_when"):
            lines += ["", "### Stop when", ""]
            lines.extend(bullet_list(rule.get("stop_when", [])))
        lines.append("")
    lines += ["## Full JSON reference", "", json_block(doc)]
    return "\n".join(lines)


def render_generic_topic(topic: str, doc: dict[str, Any]) -> str:
    lines = render_topic_header(topic, doc)
    lines += ["## Full JSON reference", "", json_block(doc)]
    return "\n".join(lines)


def render_topic(page: Path, topic: str, doc: dict[str, Any]) -> str:
    if topic == "overview":
        return render_overview(page, doc)
    if topic == "model":
        return render_model(doc)
    if topic == "command-line":
        return render_command_line(doc)
    if topic == "examples":
        return render_examples(page, doc)
    if topic == "operations":
        return render_operations_topic(page, doc)
    if topic == "capabilities":
        return render_capabilities(doc)
    if topic == "workflow-authoring":
        return render_workflow_authoring(doc)
    return render_generic_topic(topic, doc)


def render_operations_index(operation_refs: list[str], root_topics_path: Path) -> str:
    page = Path("operations/index.md")
    grouped: dict[str, list[str]] = {}
    for ref in operation_refs:
        namespace, _ = ref.split(".", 1)
        grouped.setdefault(namespace, []).append(ref)
    lines = [
        "# Operation reference",
        "",
        f"Generated operation pages for {len(operation_refs)} published operations.",
        "",
        f"- [Operation catalog]({rel_link(page, root_topics_path)})",
        "",
    ]
    for namespace in sorted(grouped):
        lines += [f"## {namespace}", "", namespace_gloss(namespace), ""]
        for ref in sorted(grouped[namespace]):
            lines.append(doc_link(ref, page, operation_doc_path(ref)))
        lines.append("")
    return "\n".join(lines)


def collect_operation_refs(operations_doc: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for connector in operations_doc.get("connectors", []):
        namespace = connector["namespace"]
        for operation in connector.get("operations", []):
            refs.append(f"{namespace}.{operation['name']}")
    return refs


def prepare_output(output_dir: Path, keep: bool) -> None:
    if output_dir.exists() and not keep:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    output_dir = args.output.resolve()

    if not ORDO_HELP.exists():
        raise SystemExit(f"Missing launcher: {ORDO_HELP}")

    prepare_output(output_dir, args.keep)

    root_doc = run_help()
    operations_doc = run_help("operations")
    operation_refs = collect_operation_refs(operations_doc)

    write(output_dir / "index.md", render_root_index(root_doc, list(STATIC_TOPICS), operation_refs))

    for topic in STATIC_TOPICS:
        doc = operations_doc if topic == "operations" else run_help(topic)
        write(output_dir / topic_doc_path(topic), render_topic(topic_doc_path(topic), topic, doc))

    write(
        output_dir / "operations/index.md",
        render_operations_index(operation_refs, topic_doc_path("operations")),
    )

    for reference in operation_refs:
        page = operation_doc_path(reference)
        doc = run_help("operation", reference)
        write(output_dir / page, render_operation(page, doc))


if __name__ == "__main__":
    main()
