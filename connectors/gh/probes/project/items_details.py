"""gh.project.items.details probe."""

from __future__ import annotations

from connectors.gh.probes.project._items import (
    fetch_project_items,
    fetch_project_items_by_content_refs,
    normalize_project_item_details,
)
from connectors.gh.probes.project.items import (
    _MISSING,
    _classify_item_filters,
    _build_field_lookup,
    _build_server_side_query,
    _matches_item_filters,
    _matches_selected_filters,
    _optional_input,
    _parse_content_refs,
    _parse_filters,
    _requested_content_modes,
)
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, probe, ok
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub project items details',
 'goal': 'A workflow needs project-scoped item matching plus richer content details that are not present on '
         'connector.gh.project.items alone.',
 'summary': 'Probe one GitHub Project as a normalized item collection with stable content details such as issue state '
            'and label names in addition to the base membership facts.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs project-scoped item matching plus richer content details that are not '
                         'present on connector.gh.project.items alone.',
                         'Later branching or publishing depends on issue or pull-request state, or on label_names for '
                         'the matched project-backed content.']},
              {'heading': 'Do not use for',
               'items': ['Cheap project membership scans where repository, number, title, and url are already enough; '
                         'use connector.gh.project.items for the lighter collection probe.',
                         'Checking or mutating one specific issue membership; use connector.gh.project.issue or '
                         'connector.gh.project.issue.* for the one-item membership family.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.project.items',
                               'summary': 'Parent collection probe for lighter normalized project items without extra '
                                          'content details'},
                              {'handle': 'connector.gh.project.issue',
                               'summary': 'Sibling probe for one issue-specific membership snapshot instead of a '
                                          'collection result set'},
                              {'handle': 'connector.gh.issue',
                               'summary': 'Sibling probe for one repository issue snapshot outside the '
                                          'project-collection context'},
                              {'handle': 'connector.gh.project.field',
                               'summary': 'Sibling probe for project field metadata rather than matched item '
                                          'details'}]},
              {'heading': 'Examples',
               'items': ['gh.project.items.details with inputs {"content_kind": "Issue", "project_id": "PVT_demo"}',
                         'gh.project.items.details with inputs {"content_kind": "Issue", "content_refs": '
                         '["owner/repo#7", "owner/repo#8"], "filters": [{"field": "Type", "value": "Task"}], '
                         '"project_id": "PVT_demo"}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.project.items', 'connector.gh.project.issue', 'connector.gh.issue']}]})

def info():
    return probe(
        name="project.items.details",
        human=HUMAN,
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
    project_filters = ()
    field_lookup: dict[str, dict[str, object]] = {}
    item_filters = ()
    if parsed_filters:
        from connectors.gh.probes.project._fields import fetch_project_fields

        fetched_fields = fetch_project_fields(ctx, project_id, diagnostic_prefix="probe.gh_project_items_details")
        if not isinstance(fetched_fields, tuple):
            return fetched_fields
        project, field_raw = fetched_fields
        raw = {**raw, "fields": field_raw}
        classified_filters = _classify_item_filters(
            ctx,
            project_id=project_id,
            project=project,
            filters=parsed_filters,
            supported_item_attributes={"item_id", "content_kind", "repository", "number", "title", "url", "state"},
        )
        if not isinstance(classified_filters, tuple):
            return classified_filters
        project_filters, item_filters = classified_filters
        field_lookup_outcome = _build_field_lookup(ctx, project_id=project_id, project=project, filters=project_filters)
        if not isinstance(field_lookup_outcome, dict):
            return field_lookup_outcome
        field_lookup = field_lookup_outcome
        search_query = _build_server_side_query(requested_kind=requested_kind, filters=project_filters, field_lookup=field_lookup)
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
        if project_filters and parsed_content_refs and not _matches_selected_filters(node, project_filters, field_lookup):
            continue
        if item_filters and not _matches_item_filters(item, item_filters):
            continue
        items.append(item)
    return ok(
        summary="GitHub project item details retrieved successfully",
        outputs={"count": len(items), "items": items},
        raw=raw,
    )
