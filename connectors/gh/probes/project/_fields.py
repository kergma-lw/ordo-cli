"""Shared GitHub Project field lookup helpers."""

from __future__ import annotations

import json

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail


def fetch_project_fields(ctx: OperationContext, project_id: str, *, diagnostic_prefix: str) -> tuple[dict[str, object], dict[str, object]] | OperationOutcome:
    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                (
                    "query="
                    "query($id:ID!){node(id:$id){... on ProjectV2{id title fields(first:100){nodes{"
                    "__typename "
                    "... on ProjectV2FieldCommon{id name dataType} "
                    "... on ProjectV2SingleSelectField{options{id name}} "
                    "... on ProjectV2IterationField{configuration{iterations{title}}}"
                    "}}}}}"
                ),
                "-f",
                f"id={project_id}",
            ],
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="probe_failed",
            summary="GitHub project field probe failed",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.command_failed",
                    level="error",
                    message="GitHub project field probe failed",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=exc.outcome.raw,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="probe_failed",
            summary="GitHub project field output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_json",
                    level="error",
                    message="GitHub project field output was not valid JSON",
                    details={"reference": ctx.reference, "project_id": project_id, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    project = ((payload.get("data") or {}).get("node"))
    if project is None:
        return fail(
            code="project_not_found",
            summary="GitHub project was not found",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.project_not_found",
                    level="error",
                    message="GitHub project was not found",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(project, dict):
        return fail(
            code="probe_failed",
            summary="GitHub project field output was not an object",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_shape",
                    level="error",
                    message="GitHub project field output was not an object",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )
    return project, command.raw


def field_nodes(project: dict[str, object]) -> list[object]:
    fields = project.get("fields")
    if not isinstance(fields, dict):
        return []
    nodes = fields.get("nodes")
    return nodes if isinstance(nodes, list) else []


def field_kind(node: dict[str, object]) -> str | None:
    typename = node.get("__typename")
    if typename == "ProjectV2SingleSelectField":
        return "single_select"
    if typename == "ProjectV2IterationField":
        return "iteration"
    data_type = node.get("dataType")
    if isinstance(data_type, str) and data_type:
        return data_type.lower()
    return None


def field_options(node: dict[str, object]) -> list[str]:
    typename = node.get("__typename")
    if typename == "ProjectV2SingleSelectField":
        options = node.get("options")
        if not isinstance(options, list):
            return []
        return [option.get("name") for option in options if isinstance(option, dict) and isinstance(option.get("name"), str)]
    if typename == "ProjectV2IterationField":
        configuration = node.get("configuration")
        if not isinstance(configuration, dict):
            return []
        iterations = configuration.get("iterations")
        if not isinstance(iterations, list):
            return []
        return [item.get("title") for item in iterations if isinstance(item, dict) and isinstance(item.get("title"), str)]
    return []
