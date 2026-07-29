"""Shared GitHub Project item enumeration helpers."""

from __future__ import annotations

import json

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail


def fetch_project_items(
    ctx: OperationContext,
    project_id: str,
    *,
    search_query: str | None = None,
    include_details: bool = False,
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
            search_query=search_query,
            include_details=include_details,
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
    search_query: str | None,
    include_details: bool,
    diagnostic_prefix: str,
):
    issue_content = "... on Issue{id number title url repository{nameWithOwner}} "
    pull_request_content = "... on PullRequest{id number title url repository{nameWithOwner}}"
    if include_details:
        issue_content = "... on Issue{id number title state url repository{nameWithOwner} labels(first:100){nodes{name}}} "
        pull_request_content = "... on PullRequest{id number title state url repository{nameWithOwner} labels(first:100){nodes{name}}}"
    query = (
        "query($id:ID!,$after:String,$search:String){"
        "node(id:$id){... on ProjectV2{"
        "items(first:100,after:$after,query:$search){pageInfo{hasNextPage endCursor} nodes{"
        "id "
        "content{"
        "__typename "
        f"{issue_content}"
        f"{pull_request_content}"
        "} "
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
    if search_query is not None:
        argv.extend(["-f", f"search={search_query}"])

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


def normalize_project_item_details(node: dict[str, object]) -> dict[str, object]:
    item = normalize_project_item(node)
    content = node.get("content")
    state = None
    label_names = None
    if isinstance(content, dict):
        state = content.get("state")
        labels = content.get("labels")
        nodes = labels.get("nodes") if isinstance(labels, dict) else None
        if isinstance(nodes, list):
            label_names = [label.get("name") for label in nodes if isinstance(label, dict) and isinstance(label.get("name"), str)]
    return {**item, "state": state, "label_names": label_names}


def fetch_project_items_by_content_refs(
    ctx: OperationContext,
    project_id: str,
    *,
    content_refs: list[dict[str, object]],
    include_issues: bool,
    include_pull_requests: bool,
    field_names: list[str],
    include_details: bool = False,
    diagnostic_prefix: str,
) -> tuple[list[dict[str, object]], dict[str, object]] | OperationOutcome:
    alias_map = {f"field_{index}": field_name for index, field_name in enumerate(field_names)}
    query = _build_content_ref_query(
        content_refs=content_refs,
        include_issues=include_issues,
        include_pull_requests=include_pull_requests,
        alias_map=alias_map,
        include_details=include_details,
    )
    try:
        command = ctx.command(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
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
            raw=command.raw,
        )

    data = payload.get("data")
    if not isinstance(data, dict):
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
            raw=command.raw,
        )

    items: list[dict[str, object]] = []
    for repo_index, content_ref in enumerate(content_refs):
        repo_data = data.get(f"repo_{repo_index}")
        if not isinstance(repo_data, dict):
            continue
        content_data = _extract_content_data(repo_data, repo_index=repo_index, include_issues=include_issues, include_pull_requests=include_pull_requests)
        if not isinstance(content_data, dict):
            continue
        project_items = ((content_data.get("projectItems") or {}).get("nodes")) if isinstance(content_data.get("projectItems"), dict) else None
        if not isinstance(project_items, list):
            continue
        content_payload = {
            "__typename": content_data.get("__typename"),
            "number": content_data.get("number"),
            "title": content_data.get("title"),
            "state": content_data.get("state"),
            "url": content_data.get("url"),
            "repository": content_data.get("repository"),
            "labels": content_data.get("labels"),
        }
        for project_item in project_items:
            if not isinstance(project_item, dict):
                continue
            project = project_item.get("project")
            if not isinstance(project, dict) or project.get("id") != project_id:
                continue
            items.append(
                {
                    "id": project_item.get("id"),
                    "content": content_payload,
                    "selected_field_values": {
                        field_name: project_item.get(alias)
                        for alias, field_name in alias_map.items()
                    },
                    "requested_ref": content_ref.get("value"),
                }
            )
    return items, command.raw


def _build_content_ref_query(
    *,
    content_refs: list[dict[str, object]],
    include_issues: bool,
    include_pull_requests: bool,
    alias_map: dict[str, str],
    include_details: bool,
) -> str:
    repo_fragments: list[str] = []
    field_selection = " ".join(
        (
            f'{alias}:fieldValueByName(name:{json.dumps(field_name)})' + "{"
            "__typename "
            "... on ProjectV2ItemFieldSingleSelectValue{name} "
            "... on ProjectV2ItemFieldIterationValue{title} "
            "... on ProjectV2ItemFieldNumberValue{number} "
            "... on ProjectV2ItemFieldTextValue{text} "
            "... on ProjectV2ItemFieldDateValue{date}"
            "}"
        )
        for alias, field_name in alias_map.items()
    )
    project_items_selection = (
        "projectItems(first:100){nodes{" "id project{... on ProjectV2{id}} " f"{field_selection}" "}}"
        if field_selection
        else "projectItems(first:100){nodes{id project{... on ProjectV2{id}}}}"
    )
    detail_fields = "state labels(first:100){nodes{name}} " if include_details else ""
    content_selection = f"__typename number title {detail_fields}url repository{{nameWithOwner}} {project_items_selection}"
    for repo_index, content_ref in enumerate(content_refs):
        owner = json.dumps(str(content_ref["owner"]))
        repo = json.dumps(str(content_ref["repo"]))
        number = int(content_ref["number"])
        content_fields: list[str] = []
        if include_issues:
            content_fields.append(f"issue_{repo_index}:issue(number:{number}){{{content_selection}}}")
        if include_pull_requests:
            content_fields.append(f"pull_{repo_index}:pullRequest(number:{number}){{{content_selection}}}")
        repo_fragments.append(f"repo_{repo_index}:repository(owner:{owner},name:{repo}){{{' '.join(content_fields)}}}")
    return f"query{{{' '.join(repo_fragments)}}}"


def _extract_content_data(
    repo_data: dict[str, object], *, repo_index: int, include_issues: bool, include_pull_requests: bool
) -> dict[str, object] | None:
    if include_issues:
        issue_data = repo_data.get(f"issue_{repo_index}")
        if isinstance(issue_data, dict):
            return issue_data
    if include_pull_requests:
        pull_request_data = repo_data.get(f"pull_{repo_index}")
        if isinstance(pull_request_data, dict):
            return pull_request_data
    return None
