"""gh.project.items probe."""

from __future__ import annotations

from connectors.gh.probes.project._items import fetch_project_items, normalize_project_item
from ordo.plugin_sdk import OperationContext, ok, probe


def info():
    return probe(
        name="project.items",
        inputs={"project_id": "string"},
        outputs={
            "count": "integer",
            "items": [
                {
                    "item_id": "string",
                    "content_kind": "string",
                    "repository": "string",
                    "number": "integer",
                    "title": "string",
                    "url": "string",
                }
            ],
        },
        failure_modes=("project_not_found", "probe_failed"),
        handler=run,
        summary="Return normalized GitHub Project items for one project membership scan",
    )


def run(ctx: OperationContext):
    project_id = str(ctx.input("project_id"))
    fetched = fetch_project_items(ctx, project_id, diagnostic_prefix="probe.gh_project_items")
    if not isinstance(fetched, tuple):
        return fetched
    nodes, raw = fetched
    items = [normalize_project_item(node) for node in nodes]
    return ok(
        summary="GitHub project items retrieved successfully",
        outputs={"count": len(items), "items": items},
        raw=raw,
    )
