"""gh.project.items probe."""

from __future__ import annotations

from collections.abc import Sequence
import re

from connectors.gh.probes.project._items import fetch_project_items, fetch_project_items_by_content_refs, normalize_project_item
from connectors.gh.probes.project._fields import fetch_project_fields, field_kind, field_nodes
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe

_MISSING = object()
_SAFE_QUERY_TOKEN = re.compile(r"^[A-Za-z0-9_.@/-]+$")
_CONTENT_REF_RE = re.compile(r"^(?P<repository>[^#/]+/[^#/]+)#(?P<number>[1-9][0-9]*)$")


class _FilterSpec(tuple[str, object]):
    @property
    def field(self) -> str:
        return self[0]

    @property
    def value(self) -> object:
        return self[1]


class _ItemFilterSpec(tuple[str, str, object]):
    @property
    def field(self) -> str:
        return self[0]

    @property
    def attribute(self) -> str:
        return self[1]

    @property
    def value(self) -> object:
        return self[2]


class _ContentRef(tuple[str, str, str, str, int]):
    @property
    def value(self) -> str:
        return self[0]

    @property
    def repository(self) -> str:
        return self[1]

    @property
    def owner(self) -> str:
        return self[2]

    @property
    def repo(self) -> str:
        return self[3]

    @property
    def number(self) -> int:
        return self[4]


_ITEM_FILTER_ALIASES = {
    "itemid": "item_id",
    "contentkind": "content_kind",
    "repository": "repository",
    "number": "number",
    "title": "title",
    "url": "url",
    "state": "state",
}

_ITEM_FILTER_TYPES = {
    "item_id": "string",
    "content_kind": "string",
    "repository": "string",
    "number": "number",
    "title": "string",
    "url": "string",
    "state": "string",
}


def info():
    return probe(
        name="project.items",
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
        summary="Return normalized GitHub Project items for one project membership scan",
        examples=(
            {
                "reference": "gh.project.items",
                "inputs": {"project_id": "PVT_demo"},
                "why": "Load normalized project membership facts without mutating project state.",
            },
            {
                "reference": "gh.project.items",
                "inputs": {
                    "project_id": "PVT_demo",
                    "content_kind": "Issue",
                    "filters": [{"field": "Status", "value": "Ready"}],
                },
                "why": "Narrow one project scan to issue-like items whose Status field equals Ready.",
            },
            {
                "reference": "gh.project.items",
                "inputs": {
                    "project_id": "PVT_demo",
                    "content_kind": "Issue",
                    "filters": [{"field": "Type", "value": "Task"}],
                    "content_refs": ["owner/repo#7", "owner/repo#8"],
                },
                "why": "Intersect one project item query with one explicit set of GitHub content references.",
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
    project_filters: tuple[_FilterSpec, ...] = ()
    field_lookup: dict[str, dict[str, object]] = {}
    item_filters: tuple[_ItemFilterSpec, ...] = ()
    if parsed_filters:
        fetched_fields = fetch_project_fields(ctx, project_id, diagnostic_prefix="probe.gh_project_items")
        if not isinstance(fetched_fields, tuple):
            return fetched_fields
        project, field_raw = fetched_fields
        raw = {**raw, "fields": field_raw}
        classified_filters = _classify_item_filters(ctx, project_id=project_id, project=project, filters=parsed_filters, supported_item_attributes={"item_id", "content_kind", "repository", "number", "title", "url"})
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
            diagnostic_prefix="probe.gh_project_items",
        )
    else:
        fetched = fetch_project_items(ctx, project_id, search_query=search_query, diagnostic_prefix="probe.gh_project_items")
    if not isinstance(fetched, tuple):
        return fetched
    nodes, fetched_raw = fetched
    raw = {**raw, **fetched_raw}

    items = []
    for node in nodes:
        item = normalize_project_item(node)
        if requested_kind is not None and item.get("content_kind") != requested_kind:
            continue
        if project_filters and parsed_content_refs and not _matches_selected_filters(node, project_filters, field_lookup):
            continue
        if item_filters and not _matches_item_filters(item, item_filters):
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


def _classify_item_filters(
    ctx: OperationContext,
    *,
    project_id: str,
    project: dict[str, object],
    filters: Sequence[_FilterSpec],
    supported_item_attributes: set[str],
) -> tuple[tuple[_FilterSpec, ...], tuple[_ItemFilterSpec, ...]] | object:
    project_field_names = {
        node.get("name")
        for node in field_nodes(project)
        if isinstance(node, dict) and isinstance(node.get("name"), str)
    }
    project_filters: list[_FilterSpec] = []
    item_filters: list[_ItemFilterSpec] = []
    for filter_spec in filters:
        if filter_spec.field in project_field_names:
            project_filters.append(filter_spec)
            continue
        attribute = _canonical_item_filter_attribute(filter_spec.field)
        if attribute is None or attribute not in supported_item_attributes:
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
        normalized_value = _normalize_item_filter_value(ctx, project_id=project_id, field=filter_spec.field, attribute=attribute, value=filter_spec.value)
        if isinstance(normalized_value, OperationOutcome):
            return normalized_value
        item_filters.append(_ItemFilterSpec((filter_spec.field, attribute, normalized_value)))
    return tuple(project_filters), tuple(item_filters)


def _canonical_item_filter_attribute(field: str) -> str | None:
    normalized = field.replace("_", "").replace(" ", "").casefold()
    return _ITEM_FILTER_ALIASES.get(normalized)


def _parse_content_refs(ctx: OperationContext, *, project_id: str, content_refs_value: object) -> tuple[_ContentRef, ...] | object:
    if content_refs_value is _MISSING:
        return ()
    if not isinstance(content_refs_value, list):
        return _invalid_content_ref(
            ctx,
            project_id=project_id,
            message="GitHub project item content_refs must be a list of OWNER/REPO#NUMBER strings",
            details={"content_refs": content_refs_value},
        )

    parsed: list[_ContentRef] = []
    for index, item in enumerate(content_refs_value):
        if not isinstance(item, str):
            return _invalid_content_ref(
                ctx,
                project_id=project_id,
                message="Each GitHub project item content_ref must be a string in OWNER/REPO#NUMBER format",
                details={"content_ref_index": index, "content_ref": item},
            )
        match = _CONTENT_REF_RE.match(item)
        if match is None:
            return _invalid_content_ref(
                ctx,
                project_id=project_id,
                message="Each GitHub project item content_ref must use OWNER/REPO#NUMBER format",
                details={"content_ref_index": index, "content_ref": item},
            )
        repository = match.group("repository")
        owner, repo = repository.split("/", 1)
        parsed.append(_ContentRef((item, repository, owner, repo, int(match.group("number")))))
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


def _build_server_side_query(
    *,
    requested_kind: str | None,
    filters: Sequence[_FilterSpec],
    field_lookup: dict[str, dict[str, object]],
) -> str | None:
    terms: list[str] = []
    kind_term = _content_kind_query_term(requested_kind)
    if kind_term is not None:
        terms.append(kind_term)
    for filter_spec in filters:
        expected = field_lookup[filter_spec.field]
        rendered = _render_query_term(filter_spec.field, expected["kind"], expected["value"])
        if rendered:
            terms.append(rendered)
    if not terms:
        return None
    return " ".join(terms)


def _requested_content_modes(requested_kind: str | None) -> tuple[bool, bool]:
    if requested_kind == "Issue":
        return True, False
    if requested_kind == "PullRequest":
        return False, True
    return True, True


def _matches_selected_filters(node: dict[str, object], filters: Sequence[_FilterSpec], field_lookup: dict[str, dict[str, object]]) -> bool:
    selected = node.get("selected_field_values")
    selected_values = selected if isinstance(selected, dict) else {}
    for filter_spec in filters:
        expected = field_lookup[filter_spec.field]
        actual = _extract_selected_field_value(selected_values.get(filter_spec.field))
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


def _matches_item_filters(item: dict[str, object], filters: Sequence[_ItemFilterSpec]) -> bool:
    for filter_spec in filters:
        actual = item.get(filter_spec.attribute)
        if filter_spec.attribute == "number":
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                return False
            if float(actual) != float(filter_spec.value):
                return False
            continue
        if actual != filter_spec.value:
            return False
    return True


def _extract_selected_field_value(value: object) -> object | None:
    if not isinstance(value, dict):
        return None
    typename = value.get("__typename")
    if typename == "ProjectV2ItemFieldSingleSelectValue":
        return value.get("name")
    if typename == "ProjectV2ItemFieldIterationValue":
        return value.get("title")
    if typename == "ProjectV2ItemFieldNumberValue":
        return value.get("number")
    if typename == "ProjectV2ItemFieldTextValue":
        return value.get("text")
    if typename == "ProjectV2ItemFieldDateValue":
        return value.get("date")
    return None


def _content_kind_query_term(requested_kind: str | None) -> str | None:
    if requested_kind == "Issue":
        return "is:issue"
    if requested_kind == "PullRequest":
        return "is:pr"
    return None


def _render_query_term(field: str, kind: object, value: object) -> str:
    qualifier = _quote_query_token(field)
    if kind == "number":
        return f"{qualifier}:{_format_number_query_value(value)}"
    return f"{qualifier}:{_quote_query_token(str(value))}"


def _format_number_query_value(value: object) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return format(numeric, "g")


def _quote_query_token(value: str) -> str:
    if _SAFE_QUERY_TOKEN.fullmatch(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


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


def _normalize_item_filter_value(ctx: OperationContext, *, project_id: str, field: str, attribute: str, value: object) -> object:
    kind = _ITEM_FILTER_TYPES[attribute]
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
            message=f"GitHub item attribute '{field}' requires a numeric filter value",
            details={"field": field, "attribute": attribute, "value": value},
        )
    if isinstance(value, str):
        return value
    return _invalid_filter_value(
        ctx,
        project_id=project_id,
        message=f"GitHub item attribute '{field}' requires a string filter value",
        details={"field": field, "attribute": attribute, "value": value},
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


def _invalid_content_ref(ctx: OperationContext, *, project_id: str, message: str, details: dict[str, object]):
    payload = {"reference": ctx.reference, "project_id": project_id, **details}
    return fail(
        code="invalid_content_ref",
        summary=message,
        diagnostics=(
            Diagnostic(
                code="probe.gh_project_items.invalid_content_ref",
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
