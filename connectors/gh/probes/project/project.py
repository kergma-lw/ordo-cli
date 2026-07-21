"""gh.project probe."""

from __future__ import annotations

import json

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="project",
        inputs={"project_id": "string"},
        outputs={
            "exists": "boolean",
            "id": "string",
            "title": "string",
        },
        failure_modes=("project_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    project_id = str(ctx.input("project_id"))

    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                "query=query($id:ID!){node(id:$id){... on ProjectV2{id title}}}",
                "-f",
                f"id={project_id}",
            ],
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="probe_failed",
            summary="GitHub project probe failed",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_project.command_failed",
                    level="error",
                    message="GitHub project probe failed",
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
            summary="GitHub project output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_project.invalid_json",
                    level="error",
                    message="GitHub project output was not valid JSON",
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
                    code="probe.gh_project.project_not_found",
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
            summary="GitHub project output was not an object",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_project.invalid_shape",
                    level="error",
                    message="GitHub project output was not an object",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )

    return ok(
        summary="GitHub project retrieved successfully",
        outputs={
            "exists": True,
            "id": project.get("id"),
            "title": project.get("title"),
        },
        raw=command.raw,
    )
