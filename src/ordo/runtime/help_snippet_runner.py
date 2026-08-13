"""Shared verification runner for world-backed help snippets."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.model.runtime import RuntimeStatus

from . import validate_workflow_text
from .help_snippet_scaffolds import build_expression_value_scaffold, build_step_field_scaffold, build_step_fragment_scaffold, build_workflow_fragment_scaffold


@dataclass(frozen=True)
class HelpSnippetRunnerResult:
    """Structured result for one world-backed help snippet verification."""

    world_name: str
    insertion_mode: str
    target: str
    workflow_text: str
    effective_world: dict[str, object]
    status: str


def verify_help_snippet(
    *,
    snippet: str,
    world: str,
    insertion_mode: str,
    target: str,
    overrides: dict[str, object] | None = None,
) -> HelpSnippetRunnerResult:
    """Verify one help snippet inside a named world and explicit insertion scaffold."""

    worlds = describe_help_snippet_worlds()
    if world not in worlds:
        raise ValueError(f"Unknown snippet world: {world}")
    effective_world = deepcopy(worlds[world])
    if overrides:
        effective_world = _deep_merge(effective_world, overrides)

    if insertion_mode == "expression_value":
        workflow_text = build_expression_value_scaffold(target=target, snippet=snippet)
    elif insertion_mode == "step_field":
        workflow_text = build_step_field_scaffold(target=target, snippet=snippet)
    elif insertion_mode == "step_fragment":
        workflow_text = build_step_fragment_scaffold(target=target, snippet=snippet)
    elif insertion_mode == "workflow_fragment":
        workflow_text = build_workflow_fragment_scaffold(target=target, snippet=snippet)
    else:
        raise ValueError(f"Unsupported insertion mode: {insertion_mode}")

    report = validate_workflow_text(workflow_text, source=f"snippet-runner:{target}:{world}")
    status = report.status.value if isinstance(report.status, RuntimeStatus) else str(report.status)
    return HelpSnippetRunnerResult(
        world_name=world,
        insertion_mode=insertion_mode,
        target=target,
        workflow_text=workflow_text,
        effective_world=effective_world,
        status=status,
    )


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = deepcopy(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = deepcopy(value)
    return merged
