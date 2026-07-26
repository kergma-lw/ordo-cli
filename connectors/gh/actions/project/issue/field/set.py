"""gh.project.issue.field.set action."""

from __future__ import annotations

import json

from connectors.gh.actions._shared import PROJECT_ISSUE_INVALIDATION
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok, preflight_observation


def info():
    return action(
        name="project.issue.field.set",
        inputs={**ISSUE_IDENTITY_INPUTS, "project_id": "string", "field": "string", "value": "json"},
        effects=("set one GitHub project issue field by field name",),
        outputs={
            "issue_ref": "string",
            "project_id": "string",
            "item_id": "string",
            "field": "string",
            "field_kind": "string",
            "value": "json",
            "changed": "boolean",
        },
        failure_modes=(
            "issue_not_found",
            "project_not_found",
            "field_not_found",
            "field_kind_unsupported",
            "field_value_invalid",
            "field_value_not_found",
            "field_update_blocked",
        ),
        invalidates_observations=PROJECT_ISSUE_INVALIDATION,
        preflight_observations=(
            preflight_observation(
                probe="gh.project.issue",
                with_={"repository": "{repository}", "issue_number": "{issue_number}", "project_id": "{project_id}"},
            ),
            preflight_observation(
                probe="gh.project.field",
                with_={"project_id": "{project_id}", "field": "{field}"},
            ),
        ),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    project_id = str(ctx.input("project_id"))
    field_name = str(ctx.input("field"))
    requested_value = ctx.input("value")

    identity = resolve_issue_identity(ctx, failure_code="field_update_blocked", diagnostic_prefix="action.gh_project_issue_field_set")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    issue_facts = _load_issue_membership(
        ctx,
        issue_ref=issue_ref,
        owner=identity.owner,
        repo=identity.repo,
        number=identity.issue_number,
    )
    if isinstance(issue_facts, OperationOutcome):
        return issue_facts

    item = _match_project_item(issue_facts.get("project_items"), project_id, field_name)
    project_field = _lookup_project_field(ctx, project_id=project_id, field_name=field_name)
    if isinstance(project_field, OperationOutcome):
        return project_field
    if item is None:
        return fail(
            code="field_update_blocked",
            summary="GitHub issue is not in the requested project",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_field_set.item_not_found",
                    level="error",
                    message="GitHub issue is not in the requested project",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id},
                ),
            ),
            raw={"issue": issue_facts.get("raw", {}), "project": project_field.get("raw", {})},
        )

    item_id = item["item_id"]
    field_kind = project_field["field_kind"]
    prepared_value = _prepare_requested_value(
        ctx,
        issue_ref=issue_ref,
        project_id=project_id,
        field_name=field_name,
        field_kind=field_kind,
        requested_value=requested_value,
        project_field=project_field,
    )
    if isinstance(prepared_value, OperationOutcome):
        return prepared_value

    if item["value"] == prepared_value["current_value"]:
        return ok(
            summary=f"GitHub project field '{field_name}' is already set",
            outputs={
                "issue_ref": issue_ref,
                "project_id": project_id,
                "item_id": item_id,
                "field": field_name,
                "field_kind": field_kind,
                "value": prepared_value["output_value"],
                "changed": False,
            },
            raw={"issue": issue_facts.get("raw", {}), "project": project_field.get("raw", {})},
        )

    mutation = _mutation_parts(field_kind, prepared_value)
    if isinstance(mutation, OperationOutcome):
        return mutation
    try:
        command = ctx.command(
            mutation["argv"](project_id=project_id, item_id=item_id, field_id=project_field["field_id"]),
            failures={"os_error": "field_update_blocked", "nonzero": "field_update_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="field_update_blocked",
            summary="Updating GitHub project field failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_field_set.command_failed",
                    level="error",
                    message="Updating GitHub project field failed",
                    details={
                        "reference": ctx.reference,
                        "issue_ref": issue_ref,
                        "project_id": project_id,
                        "field": field_name,
                        "field_kind": field_kind,
                    },
                ),
            ),
            raw=exc.outcome.raw,
        )

    updated_item_id = _extract_updated_item_id(
        ctx,
        issue_ref=issue_ref,
        project_id=project_id,
        field_name=field_name,
        command_stdout=command.stdout,
        command_raw=command.raw,
    )
    if isinstance(updated_item_id, OperationOutcome):
        return updated_item_id

    return ok(
        summary=f"Updated GitHub project field '{field_name}'",
        outputs={
            "issue_ref": issue_ref,
            "project_id": project_id,
            "item_id": updated_item_id,
            "field": field_name,
            "field_kind": field_kind,
            "value": prepared_value["output_value"],
            "changed": True,
        },
        raw={"issue": issue_facts.get("raw", {}), "project": project_field.get("raw", {}), "update": command.raw},
    )


def _load_issue_membership(ctx: OperationContext, *, issue_ref: str, owner: str, repo: str, number: int) -> dict[str, object] | OperationOutcome:
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
            failures={"os_error": "field_update_blocked", "nonzero": "field_update_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if "could not resolve to an issue" in text or "issue not found" in text or "not found" in text:
            return _issue_not_found(ctx, issue_ref=issue_ref, raw=outcome.raw)
        return fail(
            code="field_update_blocked",
            summary="Inspecting GitHub project issue membership failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_field_set.inspect_failed",
                    level="error",
                    message="Inspecting GitHub project issue membership failed",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=outcome.raw,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="field_update_blocked",
            summary="GitHub project issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_field_set.invalid_json",
                    level="error",
                    message="GitHub project issue output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    issue_data = (((payload.get("data") or {}).get("repository") or {}).get("issue"))
    if issue_data is None:
        return _issue_not_found(ctx, issue_ref=issue_ref, raw=command.raw)
    if not isinstance(issue_data, dict):
        return fail(
            code="field_update_blocked",
            summary="GitHub project issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_field_set.invalid_shape",
                    level="error",
                    message="GitHub project issue output was not an object",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )
    return {"project_items": (((issue_data.get("projectItems") or {}).get("nodes")) or []), "raw": command.raw}


def _lookup_project_field(ctx: OperationContext, *, project_id: str, field_name: str) -> dict[str, object] | OperationOutcome:
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
            failures={"os_error": "field_update_blocked", "nonzero": "field_update_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="field_update_blocked",
            summary="Inspecting GitHub project field definition failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_field_set.project_lookup_failed",
                    level="error",
                    message="Inspecting GitHub project field definition failed",
                    details={"reference": ctx.reference, "project_id": project_id, "field": field_name},
                ),
            ),
            raw=exc.outcome.raw,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="field_update_blocked",
            summary="GitHub project field output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_field_set.project_invalid_json",
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
                    code="action.gh_project_issue_field_set.project_not_found",
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
        field_kind = _field_kind(node)
        return {
            "field_id": field_id,
            "field_kind": field_kind,
            "options": _field_options(node),
            "iterations": _field_iterations(node),
            "raw": command.raw,
        }

    return fail(
        code="field_not_found",
        summary=f"GitHub project field '{field_name}' was not found",
        diagnostics=(
            Diagnostic(
                code="action.gh_project_issue_field_set.field_not_found",
                level="error",
                message="GitHub project field was not found",
                details={"reference": ctx.reference, "project_id": project_id, "field": field_name},
            ),
        ),
        raw=command.raw,
    )


def _field_kind(node: dict[str, object]) -> str:
    if isinstance(node.get("options"), list):
        return "single_select"
    if isinstance(((node.get("configuration") or {}).get("iterations")), list):
        return "iteration"
    data_type = node.get("dataType")
    if data_type == "NUMBER":
        return "number"
    return str(data_type).lower() if isinstance(data_type, str) else "unsupported"


def _field_options(node: dict[str, object]) -> list[dict[str, str]]:
    options = node.get("options")
    return [item for item in options if isinstance(item, dict)] if isinstance(options, list) else []


def _field_iterations(node: dict[str, object]) -> list[dict[str, object]]:
    iterations = ((node.get("configuration") or {}).get("iterations"))
    return [item for item in iterations if isinstance(item, dict)] if isinstance(iterations, list) else []


def _match_project_item(nodes: object, project_id: str, field_name: str) -> dict[str, object] | None:
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
        return {"item_id": item_id, "value": _project_item_field_value(node.get("fieldValues"), field_name)}
    return None


def _project_item_field_value(field_values: object, field_name: str) -> object:
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


def _prepare_requested_value(
    ctx: OperationContext,
    *,
    issue_ref: str,
    project_id: str,
    field_name: str,
    field_kind: str,
    requested_value,
    project_field: dict[str, object],
) -> dict[str, object] | OperationOutcome:
    if field_kind == "single_select":
        if not isinstance(requested_value, str) or not requested_value:
            return _value_invalid(ctx, issue_ref=issue_ref, project_id=project_id, field_name=field_name, field_kind=field_kind, value=requested_value)
        option_id = _named_id(project_field.get("options"), requested_value)
        if option_id is None:
            return _value_not_found(ctx, issue_ref=issue_ref, project_id=project_id, field_name=field_name, field_kind=field_kind, value=requested_value)
        return {"current_value": requested_value, "output_value": requested_value, "option_id": option_id}
    if field_kind == "iteration":
        if not isinstance(requested_value, str) or not requested_value:
            return _value_invalid(ctx, issue_ref=issue_ref, project_id=project_id, field_name=field_name, field_kind=field_kind, value=requested_value)
        iteration_id = _named_id(project_field.get("iterations"), requested_value, key="title")
        if iteration_id is None:
            return _value_not_found(ctx, issue_ref=issue_ref, project_id=project_id, field_name=field_name, field_kind=field_kind, value=requested_value)
        return {"current_value": requested_value, "output_value": requested_value, "iteration_id": iteration_id}
    if field_kind == "number":
        if isinstance(requested_value, bool) or not isinstance(requested_value, (int, float)):
            return _value_invalid(ctx, issue_ref=issue_ref, project_id=project_id, field_name=field_name, field_kind=field_kind, value=requested_value)
        return {"current_value": requested_value, "output_value": requested_value, "number_value": requested_value}
    return fail(
        code="field_kind_unsupported",
        summary=f"GitHub project field '{field_name}' is not a supported field kind",
        diagnostics=(
            Diagnostic(
                code="action.gh_project_issue_field_set.field_kind_unsupported",
                level="error",
                message="GitHub project field kind is not supported",
                details={"reference": ctx.reference, "project_id": project_id, "field": field_name, "field_kind": field_kind},
            ),
        ),
        raw={"project": project_field.get("raw", {})},
    )


def _named_id(items: object, value: str, *, key: str = "name") -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict) or item.get(key) != value:
            continue
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            return item_id
    return None


def _mutation_parts(field_kind: str, prepared_value: dict[str, object]) -> dict[str, object] | OperationOutcome:
    if field_kind == "single_select":
        option_id = prepared_value["option_id"]
        return {
            "argv": lambda **parts: [
                "gh",
                "api",
                "graphql",
                "-f",
                "query=mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}}){projectV2Item{id}}}",
                "-f",
                f"project={parts['project_id']}",
                "-f",
                f"item={parts['item_id']}",
                "-f",
                f"field={parts['field_id']}",
                "-f",
                f"option={option_id}",
            ]
        }
    if field_kind == "iteration":
        iteration_id = prepared_value["iteration_id"]
        return {
            "argv": lambda **parts: [
                "gh",
                "api",
                "graphql",
                "-f",
                "query=mutation($project:ID!,$item:ID!,$field:ID!,$iteration:String!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{iterationId:$iteration}}){projectV2Item{id}}}",
                "-f",
                f"project={parts['project_id']}",
                "-f",
                f"item={parts['item_id']}",
                "-f",
                f"field={parts['field_id']}",
                "-f",
                f"iteration={iteration_id}",
            ]
        }
    if field_kind == "number":
        number_value = prepared_value["number_value"]
        return {
            "argv": lambda **parts: [
                "gh",
                "api",
                "graphql",
                "-f",
                "query=mutation($project:ID!,$item:ID!,$field:ID!,$value:Float!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{number:$value}}){projectV2Item{id}}}",
                "-f",
                f"project={parts['project_id']}",
                "-f",
                f"item={parts['item_id']}",
                "-f",
                f"field={parts['field_id']}",
                "-F",
                f"value={number_value}",
            ]
        }
    return fail(code="field_kind_unsupported", summary="Unsupported GitHub project field kind")


def _extract_updated_item_id(
    ctx: OperationContext,
    *,
    issue_ref: str,
    project_id: str,
    field_name: str,
    command_stdout: str,
    command_raw: dict[str, object],
) -> str | OperationOutcome:
    try:
        payload = json.loads(command_stdout) if command_stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="field_update_blocked",
            summary="GitHub project field update output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_field_set.update_invalid_json",
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
            code="field_update_blocked",
            summary="GitHub project field update response did not contain an updated item id",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_field_set.update_missing_item",
                    level="error",
                    message="GitHub project field update response did not contain an updated item id",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "field": field_name},
                ),
            ),
            raw=command_raw,
        )
    return item_id


def _issue_not_found(ctx: OperationContext, *, issue_ref: str, raw: dict[str, object]) -> OperationOutcome:
    return fail(
        code="issue_not_found",
        summary="GitHub issue was not found",
        diagnostics=(
            Diagnostic(
                code="action.gh_project_issue_field_set.issue_not_found",
                level="error",
                message="GitHub issue was not found",
                details={"reference": ctx.reference, "issue_ref": issue_ref},
            ),
        ),
        raw=raw,
    )


def _value_invalid(ctx: OperationContext, *, issue_ref: str, project_id: str, field_name: str, field_kind: str, value) -> OperationOutcome:
    return fail(
        code="field_value_invalid",
        summary=f"GitHub project field '{field_name}' rejected the requested value",
        diagnostics=(
            Diagnostic(
                code="action.gh_project_issue_field_set.field_value_invalid",
                level="error",
                message="GitHub project field value was invalid",
                details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "field": field_name, "field_kind": field_kind, "value": value},
            ),
        ),
    )


def _value_not_found(ctx: OperationContext, *, issue_ref: str, project_id: str, field_name: str, field_kind: str, value) -> OperationOutcome:
    return fail(
        code="field_value_not_found",
        summary=f"GitHub project field '{field_name}' does not expose the requested value",
        diagnostics=(
            Diagnostic(
                code="action.gh_project_issue_field_set.field_value_not_found",
                level="error",
                message="GitHub project field did not expose the requested value",
                details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "field": field_name, "field_kind": field_kind, "value": value},
            ),
        ),
    )
