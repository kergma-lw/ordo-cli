"""gh.project probe."""

from __future__ import annotations

import json

from connectors.gh._external import fail_github_command
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub project',
 'goal': 'A workflow first needs to confirm that one GitHub Project exists before inspecting its fields, issue '
         'membership, or item collections.',
 'summary': 'Probe one GitHub Project by its stable project id and return a typed existence snapshot with the '
            'canonical id and title.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow first needs to confirm that one GitHub Project exists before inspecting its '
                         'fields, issue membership, or item collections.',
                         "Later steps need the project's canonical title or want a narrow project-identity probe "
                         'instead of jumping straight to field or membership surfaces.']},
              {'heading': 'Do not use for',
               'items': ['Inspecting one named field or its selectable values; use connector.gh.project.field or '
                         'connector.gh.project.field.option for that narrower field story.',
                         'Enumerating project items or checking whether one issue is already attached to the project; '
                         'use connector.gh.project.items or connector.gh.project.issue for membership questions.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh',
                               'summary': 'Parent GitHub connector family for issue, pull-request, and project '
                                          'operations'},
                              {'handle': 'connector.gh.project.field',
                               'summary': 'Sibling probe for one named project field rather than the project identity '
                                          'itself'},
                              {'handle': 'connector.gh.project.items',
                               'summary': 'Sibling probe for project membership collections rather than top-level '
                                          'project identity'},
                              {'handle': 'connector.gh.project.issue',
                               'summary': 'Sibling probe for whether one repository issue is already in the project'}]},
              {'heading': 'Examples', 'items': ['gh.project with inputs {"project_id": "PVT_kwDOExample"}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.project.field', 'connector.gh.project.items', 'connector.gh.project.issue']}]})

def info():
    return probe(
        name="project",
        human=HUMAN,
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
        return fail_github_command(
            ctx,
            code="probe_failed",
            summary="GitHub project probe failed",
            raw=exc.outcome.raw,
            diagnostic_code="probe.gh_project.command_failed",
            details={"project_id": project_id},
            message="GitHub project probe failed",
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
