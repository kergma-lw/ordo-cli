"""gh.project.items.details probe."""

from __future__ import annotations

from connectors.gh.probes.project._items import (
    fetch_project_items,
    fetch_project_items_by_content_refs,
    normalize_project_item_details,
)
from connectors.gh.probes.project.items import (
    _MISSING,
    _build_field_lookup,
    _build_server_side_query,
    _matches_selected_filters,
    _optional_input,
    _parse_content_refs,
    _parse_filters,
    _requested_content_modes,
)
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, probe, ok


def info():
    return probe(
        name="project.items.details",
        inputs={
            "project_id": "string",
            "content_kind": "string",
            "filters": [{"field": "string", "value": "scalar"}],
            "content_refs": ["string"],
        },
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
                    "state": "string",
                    "label_names": ["string"],
                }
            ],
        },
        failure_modes=(
            "project_not_found",
            "unknown_field",
            "ambiguous_field",
            "unsupported_field_type",
            "invalid_filter_value",
            "invalid_content_ref",
            "probe_failed",
        ),
        handler=run,
        summary="Return normalized GitHub Project items with stable content details",
        examples=(
            {
                "reference": "gh.project.items.details",
                "inputs": {"project_id": "PVT_demo", "content_kind": "Issue"},
                "why": "Load project-scoped issue details including state and labels.",
            },
            {
                "reference": "gh.project.items.details",
                "inputs": {
                    "project_id": "PVT_demo",
                    "content_kind": "Issue",
                    "filters": [{"field": "Type", "value": "Task"}],
                    "content_refs": ["owner/repo#7", "owner/repo#8"],
                },
                "why": "Load detailed facts for one explicit subset of project-backed GitHub content.",
            },
        ),
    )


def run(ctx: OperationContext):
    project_id = str(ctx.input("project_id"))
    content_kind = _optional_input(ctx, "content_kind")
    if isinstance(content_kind, MappedOutcomeError):
        return content_kind.outcome
    filters_value = _optional_input(ctx, "filters")
    if isinstance(filters_value, MappedOutcomeError):
        return filters_value.outcome
    content_refs_value = _optional_input(ctx, "content_refs")
    if isinstance(content_refs_value, MappedOutcomeError):
        return content_refs_value.outcome

    parsed_filters = _parse_filters(ctx, project_id=project_id, filters_value=filters_value)
    if not isinstance(parsed_filters, tuple):
        return parsed_filters
    parsed_content_refs = _parse_content_refs(ctx, project_id=project_id, content_refs_value=content_refs_value)
    if not isinstance(parsed_content_refs, tuple):
        return parsed_content_refs

    requested_kind = None if content_kind is _MISSING else str(content_kind)
    raw: dict[str, object] = {}
    field_lookup: dict[str, dict[str, object]] = {}
    if parsed_filters:
        from connectors.gh.probes.project._fields import fetch_project_fields

        fetched_fields = fetch_project_fields(ctx, project_id, diagnostic_prefix="probe.gh_project_items_details")
        if not isinstance(fetched_fields, tuple):
            return fetched_fields
        project, field_raw = fetched_fields
        raw = {**raw, "fields": field_raw}
        field_lookup_outcome = _build_field_lookup(ctx, project_id=project_id, project=project, filters=parsed_filters)
        if not isinstance(field_lookup_outcome, dict):
            return field_lookup_outcome
        field_lookup = field_lookup_outcome
        search_query = _build_server_side_query(requested_kind=requested_kind, filters=parsed_filters, field_lookup=field_lookup)
    else:
        search_query = _build_server_side_query(requested_kind=requested_kind, filters=(), field_lookup={})

    if parsed_content_refs:
        include_issues, include_pull_requests = _requested_content_modes(requested_kind)
        fetched = fetch_project_items_by_content_refs(
            ctx,
            project_id,
            content_refs=[{"value": ref.value, "repository": ref.repository, "owner": ref.owner, "repo": ref.repo, "number": ref.number} for ref in parsed_content_refs],
            include_issues=include_issues,
            include_pull_requests=include_pull_requests,
            field_names=list(field_lookup),
            include_details=True,
            diagnostic_prefix="probe.gh_project_items_details",
        )
    else:
        fetched = fetch_project_items(
            ctx,
            project_id,
            search_query=search_query,
            include_details=True,
            diagnostic_prefix="probe.gh_project_items_details",
        )
    if not isinstance(fetched, tuple):
        return fetched
    nodes, fetched_raw = fetched
    raw = {**raw, **fetched_raw}

    items = []
    for node in nodes:
        item = normalize_project_item_details(node)
        if requested_kind is not None and item.get("content_kind") != requested_kind:
            continue
        if parsed_filters and parsed_content_refs and not _matches_selected_filters(node, parsed_filters, field_lookup):
            continue
        items.append(item)
    return ok(
        summary="GitHub project item details retrieved successfully",
        outputs={"count": len(items), "items": items},
        raw=raw,
    )
