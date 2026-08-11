"""Shared helpers for GitHub project issue field setters."""

from __future__ import annotations

import json
from typing import Any

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._issue_identity import resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok


def load_issue_membership(
    ctx: OperationContext,
    *,
    issue_ref: str,
    owner: str,
    repo: str,
    number: int,
    failure_code: str,
    diagnostic_prefix: str,
) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                (
                    "query="
                    "query($owner:String!,$repo:String!,$number:Int!){"
                    "repository(owner:$owner,name:$repo){"
                    "issue(number:$number){"
                    "projectItems(first:50){nodes{id project{... on ProjectV2{id}} fieldValues(first:50){nodes{"
                    "... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}}"
                    "... on ProjectV2ItemFieldIterationValue{title field{... on ProjectV2IterationField{name}}}"
                    "... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2FieldCommon{name}}}"
                    "}}}}}}}"
                ),
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
                "-F",
                f"number={number}",
            ],
            failures={"os_error": failure_code, "nonzero": failure_code},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if text_mentions_not_found(text, "could not resolve to an issue", "issue not found"):
            return issue_not_found(ctx, issue_ref=issue_ref, raw=outcome.raw, diagnostic_prefix=diagnostic_prefix)
        return fail_github_command(
            ctx,
            code=failure_code,
            summary="Inspecting GitHub project issue membership failed",
            raw=outcome.raw,
            diagnostic_code=f"{diagnostic_prefix}.inspect_failed",
            details={"issue_ref": issue_ref},
            message="Inspecting GitHub project issue membership failed",
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code=failure_code,
            summary="GitHub project issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_json",
                    level="error",
                    message="GitHub project issue output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    issue_data = (((payload.get("data") or {}).get("repository") or {}).get("issue"))
    if issue_data is None:
        return issue_not_found(ctx, issue_ref=issue_ref, raw=command.raw, diagnostic_prefix=diagnostic_prefix)
    if not isinstance(issue_data, dict):
        return fail(
            code=failure_code,
            summary="GitHub project issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_shape",
                    level="error",
                    message="GitHub project issue output was not an object",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )
    return {"project_items": (((issue_data.get("projectItems") or {}).get("nodes")) or []), "raw": command.raw}


def lookup_project_field(
    ctx: OperationContext,
    *,
    project_id: str,
    field_name: str,
    failure_code: str,
    diagnostic_prefix: str,
) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                (
                    "query="
                    "query($project:ID!){"
                    "node(id:$project){... on ProjectV2{id title fields(first:50){nodes{"
                    "... on ProjectV2Field{id name dataType}"
                    "... on ProjectV2SingleSelectField{id name options{id name}}"
                    "... on ProjectV2IterationField{id name configuration{iterations{id title startDate duration}}}"
                    "}}}}}"
                ),
                "-f",
                f"project={project_id}",
            ],
            failures={"os_error": failure_code, "nonzero": failure_code},
        )
    except MappedOutcomeError as exc:
        return fail_github_command(
            ctx,
            code=failure_code,
            summary="Inspecting GitHub project field definition failed",
            raw=exc.outcome.raw,
            diagnostic_code=f"{diagnostic_prefix}.project_lookup_failed",
            details={"project_id": project_id, "field": field_name},
            message="Inspecting GitHub project field definition failed",
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code=failure_code,
            summary="GitHub project field output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.project_invalid_json",
                    level="error",
                    message="GitHub project field output was not valid JSON",
                    details={"reference": ctx.reference, "project_id": project_id, "field": field_name, "error": str(exc)},
                ),
            ),
            raw=command.raw,
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
            raw=command.raw,
        )

    fields = (((project or {}).get("fields") or {}).get("nodes")) or []
    if not isinstance(fields, list):
        fields = []
    for node in fields:
        if not isinstance(node, dict) or node.get("name") != field_name:
            continue
        field_id = node.get("id")
        if not isinstance(field_id, str) or not field_id:
            break
        return {
            "field_id": field_id,
            "field_kind": field_kind(node),
            "options": field_options(node),
            "iterations": field_iterations(node),
            "raw": command.raw,
        }

    return fail(
        code="field_not_found",
        summary=f"GitHub project field '{field_name}' was not found",
        diagnostics=(
            Diagnostic(
                code=f"{diagnostic_prefix}.field_not_found",
                level="error",
                message="GitHub project field was not found",
                details={"reference": ctx.reference, "project_id": project_id, "field": field_name},
            ),
        ),
        raw=command.raw,
    )


def field_kind(node: dict[str, object]) -> str:
    if isinstance(node.get("options"), list):
        return "single_select"
    if isinstance(((node.get("configuration") or {}).get("iterations")), list):
        return "iteration"
    data_type = node.get("dataType")
    if data_type == "NUMBER":
        return "number"
    return str(data_type).lower() if isinstance(data_type, str) else "unsupported"


def field_options(node: dict[str, object]) -> list[dict[str, str]]:
    options = node.get("options")
    return [item for item in options if isinstance(item, dict)] if isinstance(options, list) else []


def field_iterations(node: dict[str, object]) -> list[dict[str, object]]:
    iterations = ((node.get("configuration") or {}).get("iterations"))
    return [item for item in iterations if isinstance(item, dict)] if isinstance(iterations, list) else []


def match_project_item(nodes: object, project_id: str, field_name: str) -> dict[str, object] | None:
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if not isinstance(node, dict):
            continue
        project = node.get("project")
        if not isinstance(project, dict) or project.get("id") != project_id:
            continue
        item_id = node.get("id")
        if not isinstance(item_id, str) or not item_id:
            continue
        return {"item_id": item_id, "value": project_item_field_value(node.get("fieldValues"), field_name)}
    return None


def project_item_field_value(field_values: object, field_name: str) -> object:
    nodes = (((field_values or {}).get("nodes")) or []) if isinstance(field_values, dict) else []
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if not isinstance(node, dict):
            continue
        field = node.get("field")
        if not isinstance(field, dict) or field.get("name") != field_name:
            continue
        if "name" in node:
            return node.get("name")
        if "title" in node:
            return node.get("title")
        if "number" in node:
            return node.get("number")
    return None


def named_id(items: object, value: str, *, key: str = "name") -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict) or item.get(key) != value:
            continue
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            return item_id
    return None


def extract_updated_item_id(
    ctx: OperationContext,
    *,
    issue_ref: str,
    project_id: str,
    field_name: str,
    command_stdout: str,
    command_raw: dict[str, object],
    failure_code: str,
    diagnostic_prefix: str,
) -> str | OperationOutcome:
    try:
        payload = json.loads(command_stdout) if command_stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code=failure_code,
            summary="GitHub project field update output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.update_invalid_json",
                    level="error",
                    message="GitHub project field update output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "field": field_name, "error": str(exc)},
                ),
            ),
            raw=command_raw,
        )
    item_id = (((payload.get("data") or {}).get("updateProjectV2ItemFieldValue") or {}).get("projectV2Item") or {}).get("id")
    if not isinstance(item_id, str) or not item_id:
        return fail(
            code=failure_code,
            summary="GitHub project field update response did not contain an updated item id",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.update_missing_item",
                    level="error",
                    message="GitHub project field update response did not contain an updated item id",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "field": field_name},
                ),
            ),
            raw=command_raw,
        )
    return item_id


def issue_not_found(ctx: OperationContext, *, issue_ref: str, raw: dict[str, object], diagnostic_prefix: str) -> OperationOutcome:
    return fail(
        code="issue_not_found",
        summary="GitHub issue was not found",
        diagnostics=(
            Diagnostic(
                code=f"{diagnostic_prefix}.issue_not_found",
                level="error",
                message="GitHub issue was not found",
                details={"reference": ctx.reference, "issue_ref": issue_ref},
            ),
        ),
        raw=raw,
    )


def field_update_blocked_item_not_found(
    ctx: OperationContext,
    *,
    issue_ref: str,
    project_id: str,
    issue_raw: dict[str, object],
    project_raw: dict[str, object],
    diagnostic_prefix: str,
) -> OperationOutcome:
    return fail(
        code="field_update_blocked",
        summary="GitHub issue is not in the requested project",
        diagnostics=(
            Diagnostic(
                code=f"{diagnostic_prefix}.item_not_found",
                level="error",
                message="GitHub issue is not in the requested project",
                details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id},
            ),
        ),
        raw={"issue": issue_raw, "project": project_raw},
    )


def resolve_issue_and_field(
    ctx: OperationContext,
    *,
    project_id: str,
    field_name: str,
    failure_code: str,
    diagnostic_prefix: str,
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]] | OperationOutcome:
    identity = resolve_issue_identity(ctx, failure_code=failure_code, diagnostic_prefix=diagnostic_prefix)
    if isinstance(identity, OperationOutcome):
        return identity
    issue_ref = identity.issue_ref
    issue_facts = load_issue_membership(
        ctx,
        issue_ref=issue_ref,
        owner=identity.owner,
        repo=identity.repo,
        number=identity.issue_number,
        failure_code=failure_code,
        diagnostic_prefix=diagnostic_prefix,
    )
    if isinstance(issue_facts, OperationOutcome):
        return issue_facts
    project_field = lookup_project_field(
        ctx,
        project_id=project_id,
        field_name=field_name,
        failure_code=failure_code,
        diagnostic_prefix=diagnostic_prefix,
    )
    if isinstance(project_field, OperationOutcome):
        return project_field
    item = match_project_item(issue_facts.get("project_items"), project_id, field_name)
    if item is None:
        return field_update_blocked_item_not_found(
            ctx,
            issue_ref=issue_ref,
            project_id=project_id,
            issue_raw=issue_facts.get("raw", {}),
            project_raw=project_field.get("raw", {}),
            diagnostic_prefix=diagnostic_prefix,
        )
    return issue_ref, issue_facts, project_field, item


def build_single_select_mutation(*, project_id: str, item_id: str, field_id: str, option_id: str) -> list[str]:
    return [
        "gh",
        "api",
        "graphql",
        "-f",
        "query=mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}}){projectV2Item{id}}}",
        "-f",
        f"project={project_id}",
        "-f",
        f"item={item_id}",
        "-f",
        f"field={field_id}",
        "-f",
        f"option={option_id}",
    ]


def build_iteration_mutation(*, project_id: str, item_id: str, field_id: str, iteration_id: str) -> list[str]:
    return [
        "gh",
        "api",
        "graphql",
        "-f",
        "query=mutation($project:ID!,$item:ID!,$field:ID!,$iteration:String!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{iterationId:$iteration}}){projectV2Item{id}}}",
        "-f",
        f"project={project_id}",
        "-f",
        f"item={item_id}",
        "-f",
        f"field={field_id}",
        "-f",
        f"iteration={iteration_id}",
    ]


def build_number_mutation(*, project_id: str, item_id: str, field_id: str, value: int | float) -> list[str]:
    return [
        "gh",
        "api",
        "graphql",
        "-f",
        "query=mutation($project:ID!,$item:ID!,$field:ID!,$value:Float!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{number:$value}}){projectV2Item{id}}}",
        "-f",
        f"project={project_id}",
        "-f",
        f"item={item_id}",
        "-f",
        f"field={field_id}",
        "-F",
        f"value={value}",
    ]


def run_field_update(
    ctx: OperationContext,
    *,
    mutation_argv: list[str],
    issue_ref: str,
    project_id: str,
    field_name: str,
    outputs: dict[str, object],
    issue_raw: dict[str, object],
    project_raw: dict[str, object],
    failure_code: str,
    diagnostic_prefix: str,
) -> OperationOutcome:
    try:
        command = ctx.command(mutation_argv, failures={"os_error": failure_code, "nonzero": failure_code})
    except MappedOutcomeError as exc:
        return fail_github_command(
            ctx,
            code=failure_code,
            summary="Updating GitHub project field failed",
            raw=exc.outcome.raw,
            diagnostic_code=f"{diagnostic_prefix}.command_failed",
            details={"issue_ref": issue_ref, "project_id": project_id, "field": field_name},
            message="Updating GitHub project field failed",
        )
    updated_item_id = extract_updated_item_id(
        ctx,
        issue_ref=issue_ref,
        project_id=project_id,
        field_name=field_name,
        command_stdout=command.stdout,
        command_raw=command.raw,
        failure_code=failure_code,
        diagnostic_prefix=diagnostic_prefix,
    )
    if isinstance(updated_item_id, OperationOutcome):
        return updated_item_id
    return ok(
        summary=f"Updated GitHub project field '{field_name}'",
        outputs={**outputs, "item_id": updated_item_id, "changed": True},
        raw={"issue": issue_raw, "project": project_raw, "update": command.raw},
    )
