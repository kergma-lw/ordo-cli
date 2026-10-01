#!/usr/bin/env python3
"""Generate a more readable GitHub Pages-friendly Markdown site from ordo-help."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ordo.model.human import human_text
ORDO_HELP = ROOT / "ordo-help"
DEFAULT_OUTPUT = ROOT / "site-docs"
STATIC_TOPICS = (
    "features",
    "overview",
    "model",
    "workflow-rules",
    "capabilities",
    "command-line",
    "operations",
    "examples",
)

# These help routes require an input or report live discovery results, so they
# remain CLI-only rather than becoming static site pages.
CLI_ONLY_TOPICS = ("snippet-coverage", "describe", "search")

TOPIC_TITLES = {
    "features": "Workflow-authoring feature map",
    "overview": "Overview",
    "model": "Workflow model",
    "workflow-rules": "Workflow rules",
    "capabilities": "Capabilities",
    "command-line": "Command-line reference",
    "examples": "Examples",
}

TOPIC_INTROS = {
    "features": "A compact map of authoring primitives, recommended patterns, and their discovery handles.",
    "overview": "Start here for a map of the main Ordo surfaces.",
    "model": "This page outlines the main workflow contracts used in workflows, playbooks, profiles, and runtime state.",
    "workflow-rules": "Use this page when adding, changing, or reviewing workflows.",
    "capabilities": "This page shows what Ordo supports, restricts, or deprecates.",
    "command-line": "This page summarizes the public CLI surface and the main execution modes.",
    "examples": "This page collects verified examples you can inspect as reference material.",
}

TOPIC_SUMMARY_REWRITES = {
    "Start with the Ordo world map": "Start with a map of the main Ordo surfaces.",
    "Inspect the main workflow contracts": "Browse the main workflow contracts.",
    "Inspect preferred workflow rules, paired check/review passes, routine cautions, early guards, and let usage": "Browse workflow rules, from the default check/review loop to fallback cautions.",
    "Inspect supported and unsupported surfaces": "See which surfaces are supported, restricted, or deprecated.",
    "Inspect the public command-line launch surface, including distinct check and review roles": "See the public CLI surface and how check, review, plan, and run differ.",
    "Inspect the public connector catalog": "Browse the public connector operations.",
    "Inspect verified repository examples": "Browse verified workflow examples from the repository.",
}

TOPIC_USE_WHEN = {
    "features": "Use this page to choose an existing authoring primitive before introducing a fallback or a new workflow shape.",
    "overview": "Use this page first when you need to understand where to look next.",
    "model": "Use this page when you need field-level workflow contract details.",
    "workflow-rules": "Use this page when you are deciding how to structure or review a workflow.",
    "capabilities": "Use this page when you need to know whether a surface is supported, restricted, or deprecated.",
    "command-line": "Use this page when you need the public CLI entrypoints, flags, and execution modes.",
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
    "git.sync.fetch": "Fetch Git refs using an exact configured remote name, not an ad hoc URL, path, or Git option.",
    "git.sync.push": "Push a local Git branch using a configured remote name; an omitted or null remote is resolved from upstream and checked before transport.",
    "git.upstream": "Read the current branch's exact configured remote, including nested names, and local remote-tracking branch tail, not the source-side branch name.",
    "git.worktree": "Read the current Git worktree state.",
    "git.worktrees": "List Git worktrees.",
    "gh.issue": "Read a GitHub issue.",
    "gh.issue.body.append": "Append text to a GitHub issue body.",
    "gh.issue.body.replace": "Replace a GitHub issue body.",
    "gh.issue.close": "Close a GitHub issue.",
    "gh.issue.comment.add": "Add a comment to a GitHub issue.",
    "gh.issue.comments": "Read comments from a GitHub issue.",
    "gh.issue.create": "Create a GitHub issue.",
    "gh.pr": "Read pull request metadata from GitHub.",
    "gh.pr.comments": "Read regular conversation comments from a GitHub pull request.",
    "gh.pr.diff": "Read normalized change content from a GitHub pull request.",
    "gh.pr.reviews": "Read submitted reviews from a GitHub pull request.",
    "gh.pr.review_comments": "Read line-level review comments from a GitHub pull request.",
    "gh.pr.checks": "Read normalized status and check-run results from a GitHub pull request head.",
    "gh.pr.timeline": "Read normalized lifecycle events from a GitHub pull request timeline.",
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
        render_human_topic(root_doc, page),
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
        "## Operation reference",
        "",
        doc_link("All operations", page, Path("operations/index.md"), f"{len(operation_refs)} published operations"),
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
        "## Workflow check/review loop",
        "",
        doc.get("workflow_check_review_passes", {}).get("rule", ""),
        "",
    ]
    for item in doc.get("workflow_check_review_passes", {}).get("passes", []):
        lines.append(f"- `{item['command']}` — {item['purpose']}")
    lines += [
        "",
        "## Recommended next calls",
        "",
    ]
    for item in doc.get("recommended_next_calls", []):
        lines.append(f"- `{item['command']}` — {item['purpose']}")
    return "\n".join(lines)


def render_model(doc: dict[str, Any]) -> str:
    lines = render_topic_header("model", doc)
    if doc.get("document_kinds"):
        lines += ["## Published document kinds", ""]
        lines.extend(bullet_list([f"`{kind}`" for kind in doc.get("document_kinds", [])]))
        lines.append("")
    return "\n".join(lines)


def render_examples(page: Path, doc: dict[str, Any]) -> str:
    page = Path(page)
    lines = render_human_topic(doc, page).splitlines()
    example_paths = {
        f"See {example['path']}.": f"See [{example['path']}]({rel_link(page, Path(example['path']))})."
        for example in doc.get("examples", [])
    }
    return "\n".join(
        next((line.replace(source, link) for source, link in example_paths.items() if source in line), line)
        for line in lines
    )


def render_operation(page: Path, doc: dict[str, Any], authoring: dict[str, Any] | None = None) -> str:
    del authoring
    page = Path(page)
    rendered = render_human_topic(doc, page)
    exact_contract = [
        rendered,
        "",
        "## Exact machine contract",
        "",
        f"Use `ordo-help operation {doc['reference']} --json` when you need the exact machine-readable input and result contract for this operation.",
    ]
    examples = doc.get("canonical_examples", [])
    if not examples:
        return "\n".join(exact_contract)
    lines = [*exact_contract, "", "## Canonical Examples", ""]
    for example in examples:
        lines.extend([f"### {example['name']}", "", example["summary"], ""])
        language = "yaml"
        source = example.get(language)
        if source:
            lines.extend([f"```{language}", source, "```"])
    return "\n".join(lines)

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
    if authoring:
        metadata = authoring["metadata"]
        lines += ["## Authoring contract", "", metadata["definition"], ""]
        lines.extend(bullet_list(metadata.get("use_when", [])))
        lines += ["", "### Boundaries", ""]
        lines.extend(bullet_list(metadata.get("do_not_use_for", [])))
        lines.append("")
        for example in authoring.get("canonical_examples", []):
            lines += [f"### {example['name']}", "", example["summary"], "", "```yaml", example["yaml"], "```", ""]
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
    return "\n".join(lines)


def render_workflow_rules(doc: dict[str, Any]) -> str:
    lines = render_topic_header("workflow-rules", doc)
    heuristic = doc.get("heuristic", [])
    if heuristic:
        lines += ["## Workflow heuristic", ""]
        lines.extend(bullet_list(heuristic))
        lines.append("")
    for rule in doc.get("rules", doc.get("workflow_rules", [])):
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
    return "\n".join(lines)


def render_generic_topic(topic: str, doc: dict[str, Any]) -> str:
    return render_human_topic(doc)


def _human_reference(label: str, page: Path | None) -> str:
    if page is None:
        return f"`{label}`"
    if label.startswith("connector."):
        reference = label.removeprefix("connector.")
        if "." in reference and reference.split(".", 1)[0] in NAMESPACE_GLOSS:
            return f"[`{label}`]({rel_link(page, operation_doc_path(reference))})"
    if label in {*STATIC_TOPICS, "operations"}:
        return f"[`{label}`]({rel_link(page, topic_doc_path(label))})"
    return f"`ordo-help describe {label}`"


def render_human_topic(doc: dict[str, Any], page: Path | None = None) -> str:
    """Render the shared reader-facing projection without contract fallbacks."""

    human = human_text(doc, owner=str(doc.get("document_kind", "help")))
    lines = [f"# {human['title']}", "", human["goal"], "", human["summary"]]
    def render_section(section: dict[str, Any], level: int) -> None:
        if not any(section.get(key) for key in ("body", "items", "references", "examples", "subsections")):
            return
        lines.extend(["", f"{'#' * level} {section['heading']}", ""])
        if section.get("body"):
            lines.extend([section["body"], ""])
        lines.extend(bullet_list(section.get("items", []), empty=""))
        for reference in section.get("references", []):
            lines.append(f"- {_human_reference(reference['handle'], page)}: {reference['summary']}")
        lines.extend(f"- Example: {example}" for example in section.get("examples", []))
        for subsection in section.get("subsections", []):
            render_section(subsection, level + 1)

    for section in human["sections"]:
        render_section(section, 2)
    return "\n".join(lines)


def render_topic(page: Path, topic: str, doc: dict[str, Any]) -> str:
    page = Path(page)
    if topic == "operations":
        return render_operations_topic(page, doc)
    if topic in {"features", "overview", "model", "workflow-rules", "capabilities", "command-line"}:
        return render_human_topic(doc, page)
    if topic == "overview":
        return render_overview(page, doc)
    if topic == "model":
        return render_model(doc)
    if topic == "examples":
        return render_examples(page, doc)
    if topic == "capabilities":
        return render_capabilities(doc)
    if topic == "workflow-rules":
        return render_workflow_rules(doc)
    return render_generic_topic(topic, doc)


def render_operations_topic(page: Path, doc: dict[str, Any]) -> str:
    """Render the operation catalog as links to the generated operation pages."""

    human = human_text(doc, owner="operations")
    without_catalog = dict(human)
    without_catalog["sections"] = [
        section for section in human["sections"] if section["heading"] != "Catalog by namespace"
    ]
    lines = [render_human_topic({"human": without_catalog}, page), "", "## Browse operation pages", ""]
    lines.extend([
        doc_link("Full operation index", page, Path("operations/index.md")),
        "",
        "Use `ordo-help operation <namespace.operation>` to read the focused CLI reference for an operation before adding it to a workflow. Use `ordo-help operation <namespace.operation> --json` when you need its exact machine-readable input and result contract.",
        "",
        "## Catalog by namespace",
        "",
    ])
    for connector in doc.get("connectors", []):
        namespace = str(connector["namespace"])
        lines.extend([f"### {namespace}", "", namespace_gloss(namespace), ""])
        for operation in connector.get("operations", []):
            name = str(operation["name"])
            reference = f"{namespace}.{name}"
            label = f"{reference} ({operation['kind']})"
            if reference == "shell.command":
                label += " [legacy-only; do not use for new workflows]"
            lines.append(doc_link(label, page, operation_doc_path(reference)))
        lines.append("")
    return "\n".join(lines)


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


def copy_repository_examples(output_dir: Path) -> None:
    """Make repository-verified examples directly browsable from the site."""

    shutil.copytree(ROOT / "examples", output_dir / "examples", dirs_exist_ok=True)


def main() -> None:
    args = parse_args()
    output_dir = args.output.resolve()

    if not ORDO_HELP.exists():
        raise SystemExit(f"Missing launcher: {ORDO_HELP}")

    prepare_output(output_dir, args.keep)
    copy_repository_examples(output_dir)

    root_doc = run_help()
    operations_doc = run_help("operations")
    operation_refs = collect_operation_refs(operations_doc)
    from ordo.help_cli import _build_model_node_lookup

    authoring_nodes = _build_model_node_lookup()

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
        authoring = None
        if reference == "fs.file" or (doc["namespace"] == "gh" and "repository" in doc["operation"].get("inputs", {})):
            authoring = authoring_nodes[f"connector.{reference}"]
        write(output_dir / page, render_operation(page, doc, authoring))


if __name__ == "__main__":
    main()
