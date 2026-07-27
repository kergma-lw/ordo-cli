"""Shared GitHub Project item enumeration helpers."""

from __future__ import annotations

import json

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail


def fetch_project_items(
    ctx: OperationContext,
    project_id: str,
    *,
    diagnostic_prefix: str,
) -> tuple[list[dict[str, object]], dict[str, object]] | OperationOutcome:
    after: str | None = None
    pages: list[dict[str, object]] = []
    items: list[dict[str, object]] = []

    while True:
        command = _load_project_items_page(
            ctx,
            project_id,
            after=after,
            diagnostic_prefix=diagnostic_prefix,
        )
        if isinstance(command, OperationOutcome):
            return command
        pages.append(command.raw)

        try:
            payload = json.loads(command.stdout) if command.stdout else {}
        except json.JSONDecodeError as exc:
            return fail(
                code="probe_failed",
                summary="GitHub project items output was not valid JSON",
                diagnostics=(
                    Diagnostic(
                        code=f"{diagnostic_prefix}.invalid_json",
                        level="error",
                        message="GitHub project items output was not valid JSON",
                        details={"reference": ctx.reference, "project_id": project_id, "error": str(exc)},
                    ),
                ),
                raw={"pages": pages},
            )

        project = (payload.get("data") or {}).get("node")
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
                raw={"pages": pages},
            )
        if not isinstance(project, dict):
            return fail(
                code="probe_failed",
                summary="GitHub project items output was not an object",
                diagnostics=(
                    Diagnostic(
                        code=f"{diagnostic_prefix}.invalid_shape",
                        level="error",
                        message="GitHub project items output was not an object",
                        details={"reference": ctx.reference, "project_id": project_id},
                    ),
                ),
                raw={"pages": pages},
            )

        page_items = ((project.get("items") or {}).get("nodes")) if isinstance(project.get("items"), dict) else None
        if not isinstance(page_items, list):
            return fail(
                code="probe_failed",
                summary="GitHub project items list was not valid",
                diagnostics=(
                    Diagnostic(
                        code=f"{diagnostic_prefix}.invalid_items",
                        level="error",
                        message="GitHub project items list was not valid",
                        details={"reference": ctx.reference, "project_id": project_id},
                    ),
                ),
                raw={"pages": pages},
            )
        items.extend(item for item in page_items if isinstance(item, dict))

        page_info = ((project.get("items") or {}).get("pageInfo")) if isinstance(project.get("items"), dict) else None
        if not isinstance(page_info, dict):
            return fail(
                code="probe_failed",
                summary="GitHub project item pagination info was not valid",
                diagnostics=(
                    Diagnostic(
                        code=f"{diagnostic_prefix}.invalid_page_info",
                        level="error",
                        message="GitHub project item pagination info was not valid",
                        details={"reference": ctx.reference, "project_id": project_id},
                    ),
                ),
                raw={"pages": pages},
            )

        has_next = page_info.get("hasNextPage") is True
        end_cursor = page_info.get("endCursor")
        if not has_next:
            break
        if not isinstance(end_cursor, str) or not end_cursor:
            return fail(
                code="probe_failed",
                summary="GitHub project item pagination cursor was not valid",
                diagnostics=(
                    Diagnostic(
                        code=f"{diagnostic_prefix}.invalid_cursor",
                        level="error",
                        message="GitHub project item pagination cursor was not valid",
                        details={"reference": ctx.reference, "project_id": project_id},
                    ),
                ),
                raw={"pages": pages},
            )
        after = end_cursor

    return items, {"pages": pages}


def _load_project_items_page(
    ctx: OperationContext,
    project_id: str,
    *,
    after: str | None,
    diagnostic_prefix: str,
):
    query = (
        "query($id:ID!,$after:String){"
        "node(id:$id){... on ProjectV2{"
        "items(first:100,after:$after){pageInfo{hasNextPage endCursor} nodes{"
        "id "
        "content{"
        "__typename "
        "... on Issue{id number title url repository{nameWithOwner}} "
        "... on PullRequest{id number title url repository{nameWithOwner}}"
        "} "
        "fieldValues(first:100){nodes{"
        "__typename "
        "... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{id name}}} "
        "... on ProjectV2ItemFieldIterationValue{title field{... on ProjectV2IterationField{id name}}} "
        "... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2FieldCommon{id name}}} "
        "... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2FieldCommon{id name}}} "
        "... on ProjectV2ItemFieldDateValue{date field{... on ProjectV2FieldCommon{id name}}}"
        "}}"
        "}}}}}"
    )
    argv = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={query}",
        "-f",
        f"id={project_id}",
    ]
    if after is not None:
        argv.extend(["-f", f"after={after}"])

    try:
        return ctx.command(argv, failures={"os_error": "probe_failed", "nonzero": "probe_failed"})
    except MappedOutcomeError as exc:
        return fail(
            code="probe_failed",
            summary="GitHub project items probe failed",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.command_failed",
                    level="error",
                    message="GitHub project items probe failed",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=exc.outcome.raw,
        )


def normalize_project_item(node: dict[str, object]) -> dict[str, object]:
    content = node.get("content")
    content_kind = None
    repository = None
    number = None
    title = None
    url = None

    if isinstance(content, dict):
        content_kind = content.get("__typename")
        repository_data = content.get("repository")
        if isinstance(repository_data, dict):
            repository = repository_data.get("nameWithOwner")
        number = content.get("number")
        title = content.get("title")
        url = content.get("url")

    return {
        "item_id": node.get("id"),
        "content_kind": content_kind,
        "repository": repository,
        "number": number,
        "title": title,
        "url": url,
    }
