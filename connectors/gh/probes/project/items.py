"""gh.project.items probe."""

from __future__ import annotations

from collections.abc import Sequence

from connectors.gh.probes.project._items import fetch_project_items, normalize_project_item
from connectors.gh.probes.project._fields import fetch_project_fields, field_kind, field_nodes
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe

_MISSING = object()


class _FilterSpec(tuple[str, object]):
    @property
    def field(self) -> str:
        return self[0]

    @property
    def value(self) -> object:
        return self[1]


def info():
    return probe(
        name="project.items",
        inputs={"project_id": "string", "content_kind": "string", "filters": [{"field": "string", "value": "scalar"}]},
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
        failure_modes=("project_not_found", "unknown_field", "ambiguous_field", "unsupported_field_type", "invalid_filter_value", "probe_failed"),
        handler=run,
        summary="Return normalized GitHub Project items for one project membership scan",
    )


def run(ctx: OperationContext):
    project_id = str(ctx.input("project_id"))
    content_kind = _optional_input(ctx, "content_kind")
    if isinstance(content_kind, MappedOutcomeError):
        return content_kind.outcome
    filters_value = _optional_input(ctx, "filters")
    if isinstance(filters_value, MappedOutcomeError):
        return filters_value.outcome

    fetched = fetch_project_items(ctx, project_id, diagnostic_prefix="probe.gh_project_items")
    if not isinstance(fetched, tuple):
        return fetched
    nodes, raw = fetched

    parsed_filters = _parse_filters(ctx, project_id=project_id, filters_value=filters_value)
    if not isinstance(parsed_filters, tuple):
        return parsed_filters

    field_lookup: dict[str, dict[str, object]] = {}
    if parsed_filters:
        fetched_fields = fetch_project_fields(ctx, project_id, diagnostic_prefix="probe.gh_project_items")
        if not isinstance(fetched_fields, tuple):
            return fetched_fields
        project, field_raw = fetched_fields
        raw = {**raw, "fields": field_raw}
        field_lookup_outcome = _build_field_lookup(ctx, project_id=project_id, project=project, filters=parsed_filters)
        if not isinstance(field_lookup_outcome, dict):
            return field_lookup_outcome
        field_lookup = field_lookup_outcome

    items = []
    requested_kind = None if content_kind is _MISSING else str(content_kind)
    for node in nodes:
        item = normalize_project_item(node)
        if requested_kind is not None and item.get("content_kind") != requested_kind:
            continue
        if parsed_filters and not _matches_filters(node, parsed_filters, field_lookup):
            continue
        items.append(item)
    return ok(
        summary="GitHub project items retrieved successfully",
        outputs={"count": len(items), "items": items},
        raw=raw,
    )


def _optional_input(ctx: OperationContext, name: str) -> object | MappedOutcomeError:
    try:
        return ctx.input(name)
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return _MISSING
        return exc


def _parse_filters(ctx: OperationContext, *, project_id: str, filters_value: object) -> tuple[_FilterSpec, ...] | object:
    if filters_value is _MISSING:
        return ()
    if not isinstance(filters_value, list):
        return _invalid_filter_value(
            ctx,
            project_id=project_id,
            message="GitHub project item filters must be a list of {field, value} objects",
            details={"filters": filters_value},
        )

    parsed: list[_FilterSpec] = []
    for index, item in enumerate(filters_value):
        if not isinstance(item, dict):
            return _invalid_filter_value(
                ctx,
                project_id=project_id,
                message="Each GitHub project item filter must be an object with field and value",
                details={"filter_index": index, "filter": item},
            )
        field = item.get("field")
        if not isinstance(field, str) or not field:
            return _invalid_filter_value(
                ctx,
                project_id=project_id,
                message="Each GitHub project item filter must declare a non-empty field name",
                details={"filter_index": index, "filter": item},
            )
        if "value" not in item or not _is_supported_filter_literal(item.get("value")):
            return _invalid_filter_value(
                ctx,
                project_id=project_id,
                message="Each GitHub project item filter must declare a scalar string or number value",
                details={"filter_index": index, "filter": item},
            )
        parsed.append(_FilterSpec((field, item.get("value"))))
    return tuple(parsed)


def _build_field_lookup(
    ctx: OperationContext,
    *,
    project_id: str,
    project: dict[str, object],
    filters: Sequence[_FilterSpec],
) -> dict[str, dict[str, object]] | object:
    lookup: dict[str, dict[str, object]] = {}
    for filter_spec in filters:
        if filter_spec.field in lookup:
            continue
        matches = [node for node in field_nodes(project) if isinstance(node, dict) and node.get("name") == filter_spec.field]
        if not matches:
            return fail(
                code="unknown_field",
                summary=f"GitHub project field '{filter_spec.field}' was not found",
                diagnostics=(
                    Diagnostic(
                        code="probe.gh_project_items.unknown_field",
                        level="error",
                        message="GitHub project field was not found",
                        details={"reference": ctx.reference, "project_id": project_id, "field": filter_spec.field},
                    ),
                ),
            )
        if len(matches) > 1:
            return fail(
                code="ambiguous_field",
                summary=f"GitHub project field '{filter_spec.field}' was ambiguous",
                diagnostics=(
                    Diagnostic(
                        code="probe.gh_project_items.ambiguous_field",
                        level="error",
                        message="GitHub project field name resolved ambiguously",
                        details={"reference": ctx.reference, "project_id": project_id, "field": filter_spec.field, "matches": len(matches)},
                    ),
                ),
            )
        field = matches[0]
        kind = field_kind(field)
        if kind not in {"single_select", "number", "text", "date", "iteration"}:
            return fail(
                code="unsupported_field_type",
                summary=f"GitHub project field '{filter_spec.field}' uses an unsupported filter type",
                diagnostics=(
                    Diagnostic(
                        code="probe.gh_project_items.unsupported_field_type",
                        level="error",
                        message="GitHub project field type is not supported for filtering",
                        details={"reference": ctx.reference, "project_id": project_id, "field": filter_spec.field, "kind": kind},
                    ),
                ),
            )
        normalized_value = _normalize_filter_value(ctx, project_id=project_id, field=filter_spec.field, kind=kind, value=filter_spec.value)
        if isinstance(normalized_value, OperationOutcome):
            return normalized_value
        lookup[filter_spec.field] = {"kind": kind, "value": normalized_value}
    return lookup


def _matches_filters(node: dict[str, object], filters: Sequence[_FilterSpec], field_lookup: dict[str, dict[str, object]]) -> bool:
    values = _item_field_values(node)
    for filter_spec in filters:
        expected = field_lookup[filter_spec.field]
        actual = values.get(filter_spec.field)
        if actual is None:
            return False
        if expected["kind"] == "number":
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                return False
            if float(actual) != float(expected["value"]):
                return False
            continue
        if actual != expected["value"]:
            return False
    return True


def _item_field_values(node: dict[str, object]) -> dict[str, object]:
    values: dict[str, object] = {}
    field_values = node.get("fieldValues")
    nodes = field_values.get("nodes") if isinstance(field_values, dict) else None
    if not isinstance(nodes, list):
        return values
    for field_value in nodes:
        if not isinstance(field_value, dict):
            continue
        field = field_value.get("field")
        if not isinstance(field, dict):
            continue
        name = field.get("name")
        if not isinstance(name, str) or not name:
            continue
        typename = field_value.get("__typename")
        if typename == "ProjectV2ItemFieldSingleSelectValue":
            values[name] = field_value.get("name")
        elif typename == "ProjectV2ItemFieldIterationValue":
            values[name] = field_value.get("title")
        elif typename == "ProjectV2ItemFieldNumberValue":
            values[name] = field_value.get("number")
        elif typename == "ProjectV2ItemFieldTextValue":
            values[name] = field_value.get("text")
        elif typename == "ProjectV2ItemFieldDateValue":
            values[name] = field_value.get("date")
    return values


def _normalize_filter_value(ctx: OperationContext, *, project_id: str, field: str, kind: str | None, value: object) -> object:
    if kind == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            try:
                return float(stripped)
            except ValueError:
                pass
        return _invalid_filter_value(
            ctx,
            project_id=project_id,
            message=f"GitHub project field '{field}' requires a numeric filter value",
            details={"field": field, "kind": kind, "value": value},
        )
    if isinstance(value, str):
        return value
    return _invalid_filter_value(
        ctx,
        project_id=project_id,
        message=f"GitHub project field '{field}' requires a string filter value",
        details={"field": field, "kind": kind, "value": value},
    )


def _invalid_filter_value(ctx: OperationContext, *, project_id: str, message: str, details: dict[str, object]):
    payload = {"reference": ctx.reference, "project_id": project_id, **details}
    return fail(
        code="invalid_filter_value",
        summary=message,
        diagnostics=(
            Diagnostic(
                code="probe.gh_project_items.invalid_filter_value",
                level="error",
                message=message,
                details=payload,
            ),
        ),
    )


def _is_supported_filter_literal(value: object) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (str, int, float))
