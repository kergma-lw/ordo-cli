"""gh.project.field probe."""

from __future__ import annotations

from connectors.gh.probes.project._fields import fetch_project_fields, field_kind, field_nodes, field_options
from ordo.plugin_sdk import OperationContext, ok, probe


def info():
    return probe(
        name="project.field",
        inputs={"project_id": "string", "field": "string"},
        outputs={
            "exists": "boolean",
            "name": "string",
            "kind": "string",
            "options": ["string"],
        },
        failure_modes=("project_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext):
    project_id = str(ctx.input("project_id"))
    field_name = str(ctx.input("field"))
    fetched = fetch_project_fields(ctx, project_id, diagnostic_prefix="probe.gh_project_field")
    if not isinstance(fetched, tuple):
        return fetched
    project, raw = fetched

    for node in field_nodes(project):
        if not isinstance(node, dict):
            continue
        if node.get("name") != field_name:
            continue
        return ok(
            summary="GitHub project field facts retrieved successfully",
            outputs={
                "exists": True,
                "name": node.get("name"),
                "kind": field_kind(node),
                "options": field_options(node),
            },
            raw=raw,
        )

    return ok(
        summary="GitHub project field was not found",
        outputs={
            "exists": False,
            "name": None,
            "kind": None,
            "options": [],
        },
        raw=raw,
    )
