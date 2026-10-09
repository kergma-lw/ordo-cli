"""Generate the compact Ordo-owned portion of repository agent instructions."""

from __future__ import annotations

from pathlib import Path

from ordo.playbook import (
    PLAYBOOK_DISCOVERY_PATH,
    discover_playbook_path,
    inspect_playbook_workflow,
    list_playbook_workflows,
)


BEGIN_MARKER = "<!-- BEGIN ORDO MANAGED SECTION -->"
END_MARKER = "<!-- END ORDO MANAGED SECTION -->"


class AgentInstructionsError(ValueError):
    """Raised when repository instructions cannot be safely generated or updated."""


def render_agent_instructions(*, playbook_path: str | Path | None = None) -> tuple[str, Path]:
    """Render the managed section from declared workflow discovery data."""

    path = Path(playbook_path) if playbook_path is not None else discover_playbook_path()
    # Launch examples use the same detailed public input contracts as workflows show.
    entries = tuple(
        inspect_playbook_workflow(entry.workflow_name, playbook_path=path)
        for entry in list_playbook_workflows(playbook_path=path)
    )
    lines = [
        BEGIN_MARKER,
        "## Ordo workflows",
        "",
        "Ordo workflows are the canonical operational entrypoints for this repository.",
        "When a workflow covers the task, use it instead of reproducing its checks manually.",
        "",
        "### Command line",
        "",
        "- Discover workflow entries → `ordo-playbook workflows list`",
        "- Inspect one workflow contract → `ordo-playbook workflows show <workflow>`",
        "- Check, named review, plan, and next can run probes and connector bootstrap commands. Use them only for trusted repository content and without maintainer credentials when inspecting a foreign pull request. Explain is static and does not run probes, read state, or execute actions.",
        "- Execute a workflow → `ordo-playbook run <workflow>`",
        "- Suggest the next workflow → `ordo-playbook next`",
        "- Show workflow connections → `ordo-playbook graph`",
        "- Read the detailed reference → `ordo-help`",
        "- Pass caller values with repeatable `--input KEY=VALUE`; use `--input-file KEY=PATH` for raw file content.",
    ]
    categories: dict[str, list[object]] = {}
    for entry in entries:
        category = entry.workflow_category or "Other"
        categories.setdefault(category, []).append(entry)
    for category, category_entries in categories.items():
        lines.extend(["", f"### {category}", ""])
        for entry in category_entries:
            need = entry.workflow_description or entry.workflow_when or entry.workflow_name
            lines.append(f"- {need} → `{_launch_example(entry)}`")
    lines.extend([
        "",
        "### Operating rules",
        "",
        "- Use `ordo-playbook workflows list` as the default discovery surface.",
        "- If no workflow in this section is an obvious match, say that no known matching workflow is available. Do not invoke discovery merely to search for one, invent a workflow, or silently replace a workflow with a manual command sequence.",
        "- Do not run unrelated preflight commands or replace a suitable workflow with a guessed manual command sequence.",
        "- Do not replace a missing or unknown workflow with a self-chosen direct command, helper script, or legacy command just because the intent seems clear.",
        "- If no suitable workflow exists, use `.AGENTS.md.pre-ordo-backup` only as reference material, inspect the current Ordo help and discovery surface, propose the missing workflow, and discuss it before using any legacy procedure directly.",
        "- Do not treat legacy helper scripts or TUI commands as the primary interface.",
        "- Use a direct command or temporary legacy bypass only when the user explicitly asks for or approves it.",
        END_MARKER,
    ])
    return "\n".join(lines) + "\n", _repository_root(path)


def update_agent_instructions(*, section: str, repository_root: Path) -> tuple[Path, str]:
    """Replace exactly one managed section or append it to repository AGENTS.md."""

    target = repository_root / "AGENTS.md"
    if not target.exists():
        target.write_text(section, encoding="utf-8")
        return target, "created"
    original = target.read_text(encoding="utf-8")
    begin_count = original.count(BEGIN_MARKER)
    end_count = original.count(END_MARKER)
    if begin_count != end_count or begin_count > 1:
        raise AgentInstructionsError(
            f"{target} must contain either no managed markers or exactly one matching marker pair"
        )
    if begin_count == 0:
        separator = "" if not original or original.endswith("\n") else "\n"
        target.write_text(f"{original}{separator}\n{section}", encoding="utf-8")
        return target, "added"
    begin = original.index(BEGIN_MARKER)
    try:
        end = original.index(END_MARKER, begin) + len(END_MARKER)
    except ValueError as exc:
        raise AgentInstructionsError(f"{target} has an invalid managed marker order") from exc
    replacement = original[:begin] + section.rstrip("\n") + original[end:]
    target.write_text(replacement, encoding="utf-8")
    return target, "updated"


def _repository_root(playbook_path: Path) -> Path:
    if playbook_path.parent.name == Path(PLAYBOOK_DISCOVERY_PATH).parent.name:
        return playbook_path.parent.parent
    return playbook_path.parent


def _launch_example(entry: object) -> str:
    workflow_name = getattr(entry, "workflow_name")
    command = f"ordo-playbook run {workflow_name}"
    for item in getattr(entry, "inputs"):
        contract = getattr(item, "contract")
        caller_slot = contract.get("caller_slot") if isinstance(contract, dict) else None
        if caller_slot not in {"required", "optional"}:
            continue
        name = getattr(item, "name")
        placeholder = _input_placeholder(name, contract)
        fragment = f"--input {name}=<{placeholder}>"
        command += f" {fragment}" if caller_slot == "required" else f" [{fragment}]"
    return command


def _input_placeholder(name: str, contract: dict[str, object]) -> str:
    allowed_values = contract.get("allowed_values")
    if isinstance(allowed_values, list) and allowed_values and all(isinstance(value, str) for value in allowed_values):
        return "|".join(allowed_values)
    return name.replace("_", "-")
