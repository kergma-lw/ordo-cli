"""Shared verification runner for world-backed help snippets."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import tempfile

import yaml

from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.model.runtime import RuntimeStatus
from ordo.routines import load_routine_registry

from . import load_workflow_file, validate_workflow_semantics, validate_workflow_text
from .loading import load_yaml_document
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

    if insertion_mode == "routine_bundle":
        return _verify_routine_bundle_snippet(snippet=snippet, world=world, target=target, effective_world=effective_world)

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


def _verify_routine_bundle_snippet(*, snippet: str, world: str, target: str, effective_world: dict[str, object]) -> HelpSnippetRunnerResult:
    if target != "routine":
        raise ValueError(f"Unsupported routine bundle target: {target}")
    payload = load_yaml_document(snippet, source=f"snippet-bundle:{target}:{world}")
    if not isinstance(payload, dict):
        raise ValueError("Routine bundle snippet must be a mapping")
    routine_id = payload.get("routine_id")
    registry_entry = payload.get("registry_entry")
    implementation_path = payload.get("implementation_path")
    implementation_text = payload.get("implementation_text")
    workflow_step = payload.get("workflow_step")
    sample_args = payload.get("sample_args", {})
    expected_stdout_json = payload.get("expected_stdout_json", {})
    if not isinstance(routine_id, str) or not routine_id:
        raise ValueError("Routine bundle snippet must declare non-empty routine_id")
    if not isinstance(registry_entry, dict):
        raise ValueError("Routine bundle snippet must declare registry_entry object")
    if not isinstance(implementation_path, str) or not implementation_path:
        raise ValueError("Routine bundle snippet must declare implementation_path")
    if not isinstance(implementation_text, str) or not implementation_text:
        raise ValueError("Routine bundle snippet must declare implementation_text")
    if workflow_step is not None and not isinstance(workflow_step, str):
        raise ValueError("Routine bundle workflow_step must be a string when present")
    if not isinstance(sample_args, dict):
        raise ValueError("Routine bundle sample_args must be an object when present")
    if not isinstance(expected_stdout_json, dict):
        raise ValueError("Routine bundle expected_stdout_json must be an object when present")

    with tempfile.TemporaryDirectory(prefix="ordo-help-routine-") as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        routines_path = tmpdir / ".ordo" / "routines.yaml"
        implementation_file = tmpdir / implementation_path
        routines_path.parent.mkdir(parents=True, exist_ok=True)
        implementation_file.parent.mkdir(parents=True, exist_ok=True)
        routines_payload = {"version": 1, "routines": {routine_id: registry_entry}}
        routines_path.write_text(yaml.safe_dump(routines_payload, sort_keys=False), encoding="utf-8")
        implementation_file.write_text(implementation_text, encoding="utf-8")
        os.chmod(implementation_file, 0o755)

        workflow_text = ""
        status = "ok"
        if isinstance(workflow_step, str) and workflow_step:
            workflow_text = build_step_fragment_scaffold(target="routine", snippet=workflow_step)
            workflow_path = tmpdir / "snippet-routine-bundle.yaml"
            workflow_path.write_text(workflow_text, encoding="utf-8")
            workflow = load_workflow_file(workflow_path, launch_dir=tmpdir)
            report = validate_workflow_semantics(workflow, source=str(workflow_path))
            status = report.status.value if isinstance(report.status, RuntimeStatus) else str(report.status)
            if status != "ok":
                return HelpSnippetRunnerResult(
                    world_name=world,
                    insertion_mode="routine_bundle",
                    target=target,
                    workflow_text=workflow_text,
                    effective_world=effective_world,
                    status=status,
                )

        registry = load_routine_registry(cwd=tmpdir)
        entry = registry.routines[routine_id]
        entrypoint = tmpdir / entry.implementation.argv[0]
        if not entrypoint.exists():
            return HelpSnippetRunnerResult(
                world_name=world,
                insertion_mode="routine_bundle",
                target=target,
                workflow_text=workflow_text,
                effective_world=effective_world,
                status="validation_error",
            )

        argv = _materialize_bundle_argv(entry.implementation.argv, sample_args, project_root=tmpdir)
        completed = subprocess.run(argv, cwd=tmpdir, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return HelpSnippetRunnerResult(
                world_name=world,
                insertion_mode="routine_bundle",
                target=target,
                workflow_text=workflow_text,
                effective_world=effective_world,
                status="execution_error",
            )
        if isinstance(entry.outputs, dict) and entry.outputs.get("mode") == "data":
            observed = load_yaml_document(completed.stdout, source=f"routine-bundle-stdout:{routine_id}")
            if not isinstance(observed, dict):
                return HelpSnippetRunnerResult(
                    world_name=world,
                    insertion_mode="routine_bundle",
                    target=target,
                    workflow_text=workflow_text,
                    effective_world=effective_world,
                    status="execution_error",
                )
            for key, value in expected_stdout_json.items():
                if observed.get(key) != value:
                    return HelpSnippetRunnerResult(
                        world_name=world,
                        insertion_mode="routine_bundle",
                        target=target,
                        workflow_text=workflow_text,
                        effective_world=effective_world,
                        status="execution_error",
                    )

        return HelpSnippetRunnerResult(
            world_name=world,
            insertion_mode="routine_bundle",
            target=target,
            workflow_text=workflow_text,
            effective_world=effective_world,
            status="ok",
        )


_ROUTINE_ARG_TOKEN = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def _materialize_bundle_argv(argv: tuple[str, ...], sample_args: dict[str, object], *, project_root: Path) -> list[str]:
    materialized: list[str] = []
    for index, item in enumerate(argv):
        token = _ROUTINE_ARG_TOKEN.fullmatch(item)
        if token is not None:
            arg_name = token.group(1)
            materialized.append(str(sample_args[arg_name]))
            continue
        if index == 0:
            materialized.append(str(project_root / item))
            continue
        materialized.append(item)
    return materialized


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = deepcopy(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = deepcopy(value)
    return merged
