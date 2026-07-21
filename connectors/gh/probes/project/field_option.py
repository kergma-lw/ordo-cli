"""gh.project.field.option probe."""

from __future__ import annotations

from connectors.gh.probes.project._fields import fetch_project_fields, field_nodes, field_options
from ordo.plugin_sdk import OperationContext, ok, probe


def info():
    return probe(
        name="project.field.option",
        inputs={"project_id": "string", "field": "string", "option": "string"},
        outputs={"exists": "boolean"},
        failure_modes=("project_not_found", "probe_failed"),
        handler=run,
        summary="Return whether one named option exists in one GitHub Project field",
    )


def run(ctx: OperationContext):
    project_id = str(ctx.input("project_id"))
    field_name = str(ctx.input("field"))
    option_name = str(ctx.input("option"))
    fetched = fetch_project_fields(ctx, project_id, diagnostic_prefix="probe.gh_project_field_option")
    if not isinstance(fetched, tuple):
        return fetched
    project, raw = fetched

    for node in field_nodes(project):
        if not isinstance(node, dict):
            continue
        if node.get("name") != field_name:
            continue
        return ok(
            summary="GitHub project field option fact retrieved successfully",
            outputs={"exists": option_name in field_options(node)},
            raw=raw,
        )

    return ok(
        summary="GitHub project field option was not found",
        outputs={"exists": False},
        raw=raw,
    )
