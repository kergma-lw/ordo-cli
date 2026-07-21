"""gh.project.issue.status.set action."""

from __future__ import annotations

import json

from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok


def info():
    return action(
        name="project.issue.status.set",
        inputs={**ISSUE_IDENTITY_INPUTS, "project_id": "string", "status": "string"},
        effects=("set GitHub project issue status",),
        outputs={"issue_ref": "string", "project_id": "string", "item_id": "string", "status": "string", "changed": "boolean"},
        failure_modes=("issue_not_found", "project_not_found", "status_not_found", "status_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    project_id = str(ctx.input("project_id"))
    requested_status = str(ctx.input("status"))

    identity = resolve_issue_identity(ctx, failure_code="status_blocked", diagnostic_prefix="action.gh_project_issue_status_set")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    owner = identity.owner
    repo = identity.repo
    number = identity.issue_number
    issue_facts = _load_issue_membership(ctx, issue_ref=issue_ref, owner=owner, repo=repo, number=number)
    if isinstance(issue_facts, OperationOutcome):
        return issue_facts

    item = _match_project_item(issue_facts.get("project_items"), project_id)
    if item is None:
        project_lookup = _lookup_project_status_field(ctx, project_id=project_id)
        if isinstance(project_lookup, OperationOutcome):
            return project_lookup
        return fail(
            code="status_blocked",
            summary="GitHub issue is not in the requested project",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.item_not_found",
                    level="error",
                    message="GitHub issue is not in the requested project",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id},
                ),
            ),
            raw={"issue": issue_facts.get("raw", {}), "project": project_lookup.get("raw", {})},
        )

    item_id = item["item_id"]
    current_status = item["status"]
    if current_status == requested_status:
        return ok(
            summary="GitHub project issue status is already set",
            outputs={
                "issue_ref": issue_ref,
                "project_id": project_id,
                "item_id": item_id,
                "status": requested_status,
                "changed": False,
            },
            raw={"issue": issue_facts.get("raw", {})},
        )

    project_lookup = _lookup_project_status_field(ctx, project_id=project_id)
    if isinstance(project_lookup, OperationOutcome):
        return project_lookup
    option_id = _status_option_id(project_lookup.get("options"), requested_status)
    if option_id is None:
        return fail(
            code="status_not_found",
            summary=f"GitHub project status '{requested_status}' was not found",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.status_not_found",
                    level="error",
                    message="GitHub project status was not found",
                    details={"reference": ctx.reference, "project_id": project_id, "status": requested_status},
                ),
            ),
            raw={"project": project_lookup.get("raw", {})},
        )

    try:
        command = ctx.command(
            [
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
                f"field={project_lookup['field_id']}",
                "-f",
                f"option={option_id}",
            ],
            failures={"os_error": "status_blocked", "nonzero": "status_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="status_blocked",
            summary="Updating GitHub project issue status failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.command_failed",
                    level="error",
                    message="Updating GitHub project issue status failed",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "status": requested_status},
                ),
            ),
            raw=exc.outcome.raw,
        )

    updated_item_id = _extract_updated_item_id(
        ctx,
        issue_ref=issue_ref,
        project_id=project_id,
        requested_status=requested_status,
        command_stdout=command.stdout,
        command_raw=command.raw,
    )
    if isinstance(updated_item_id, OperationOutcome):
        return updated_item_id

    return ok(
        summary="Updated GitHub project issue status",
        outputs={
            "issue_ref": issue_ref,
            "project_id": project_id,
            "item_id": updated_item_id,
            "status": requested_status,
            "changed": True,
        },
        raw={"issue": issue_facts.get("raw", {}), "project": project_lookup.get("raw", {}), "update": command.raw},
    )
def _load_issue_membership(
    ctx: OperationContext, *, issue_ref: str, owner: str, repo: str, number: int
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
                    "projectItems(first:50){nodes{id project{... on ProjectV2{id}} fieldValues(first:50){nodes{... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}}}}}"
                    "}}}}"
                ),
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
                "-F",
                f"number={number}",
            ],
            failures={"os_error": "status_blocked", "nonzero": "status_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if outcome.status == "status_blocked" and (
            "could not resolve to an issue" in text or "issue not found" in text or "not found" in text
        ):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_project_issue_status_set.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail(
            code="status_blocked",
            summary="Inspecting GitHub project issue membership failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.inspect_failed",
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
            code="status_blocked",
            summary="GitHub project issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.invalid_json",
                    level="error",
                    message="GitHub project issue output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    issue_data = (((payload.get("data") or {}).get("repository") or {}).get("issue"))
    if issue_data is None:
        return fail(
            code="issue_not_found",
            summary="GitHub issue was not found",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.issue_not_found",
                    level="error",
                    message="GitHub issue was not found",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )
    if not isinstance(issue_data, dict):
        return fail(
            code="status_blocked",
            summary="GitHub project issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.invalid_shape",
                    level="error",
                    message="GitHub project issue output was not an object",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    return {"project_items": (((issue_data.get("projectItems") or {}).get("nodes")) or []), "raw": command.raw}


def _match_project_item(nodes: object, project_id: str) -> dict[str, str | None] | None:
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if not isinstance(node, dict):
            continue
        project = node.get("project")
        if not isinstance(project, dict) or project.get("id") != project_id:
            continue
        item_id = node.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            continue
        status = None
        field_values = (((node.get("fieldValues") or {}).get("nodes")) or [])
        if isinstance(field_values, list):
            for field_value in field_values:
                if not isinstance(field_value, dict):
                    continue
                field = field_value.get("field")
                if not isinstance(field, dict) or field.get("name") != "Status":
                    continue
                name = field_value.get("name")
                status = name if isinstance(name, str) else None
                break
        return {"item_id": item_id, "status": status}
    return None


def _lookup_project_status_field(ctx: OperationContext, *, project_id: str) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                "query=query($id:ID!){node(id:$id){... on ProjectV2{id title fields(first:50){nodes{... on ProjectV2SingleSelectField{id name options{id name}}}}}}}",
                "-f",
                f"id={project_id}",
            ],
            failures={"os_error": "status_blocked", "nonzero": "status_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="status_blocked",
            summary="Inspecting GitHub project failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.project_lookup_failed",
                    level="error",
                    message="Inspecting GitHub project failed",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=exc.outcome.raw,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="status_blocked",
            summary="GitHub project output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.project_invalid_json",
                    level="error",
                    message="GitHub project output was not valid JSON",
                    details={"reference": ctx.reference, "project_id": project_id, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    project = ((payload.get("data") or {}).get("node"))
    if project is None:
        return fail(
            code="project_not_found",
            summary="GitHub project was not found",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.project_not_found",
                    level="error",
                    message="GitHub project was not found",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )
    if not isinstance(project, dict):
        return fail(
            code="status_blocked",
            summary="GitHub project output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.project_invalid_shape",
                    level="error",
                    message="GitHub project output was not an object",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )

    field_nodes = (((project.get("fields") or {}).get("nodes")) or [])
    if not isinstance(field_nodes, list):
        return fail(
            code="status_not_found",
            summary="GitHub project status field was not found",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.field_missing",
                    level="error",
                    message="GitHub project status field was not found",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )

    for field in field_nodes:
        if not isinstance(field, dict):
            continue
        if field.get("name") != "Status":
            continue
        field_id = field.get("id")
        if not isinstance(field_id, str) or not field_id.strip():
            break
        return {"field_id": field_id, "options": field.get("options") or [], "raw": command.raw}

    return fail(
        code="status_not_found",
        summary="GitHub project status field was not found",
        diagnostics=(
            Diagnostic(
                code="action.gh_project_issue_status_set.field_missing",
                level="error",
                message="GitHub project status field was not found",
                details={"reference": ctx.reference, "project_id": project_id},
            ),
        ),
        raw=command.raw,
    )


def _status_option_id(options: object, requested_status: str) -> str | None:
    if not isinstance(options, list):
        return None
    for option in options:
        if not isinstance(option, dict):
            continue
        if option.get("name") != requested_status:
            continue
        option_id = option.get("id")
        if isinstance(option_id, str) and option_id.strip():
            return option_id
    return None


def _extract_updated_item_id(
    ctx: OperationContext,
    *,
    issue_ref: str,
    project_id: str,
    requested_status: str,
    command_stdout: str,
    command_raw: dict[str, object],
) -> str | OperationOutcome:
    try:
        payload = json.loads(command_stdout) if command_stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="status_blocked",
            summary="GitHub project status update output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.update_invalid_json",
                    level="error",
                    message="GitHub project status update output was not valid JSON",
                    details={
                        "reference": ctx.reference,
                        "issue_ref": issue_ref,
                        "project_id": project_id,
                        "status": requested_status,
                        "error": str(exc),
                    },
                ),
            ),
            raw=command_raw,
        )

    item = (((payload.get("data") or {}).get("updateProjectV2ItemFieldValue") or {}).get("projectV2Item"))
    if not isinstance(item, dict):
        return fail(
            code="status_blocked",
            summary="GitHub project status update output was missing the updated item",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.item_missing",
                    level="error",
                    message="GitHub project status update output was missing the updated item",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "status": requested_status},
                ),
            ),
            raw=command_raw,
        )
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        return fail(
            code="status_blocked",
            summary="GitHub project status update output did not include a usable item id",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_status_set.item_id_missing",
                    level="error",
                    message="GitHub project status update output did not include a usable item id",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "status": requested_status},
                ),
            ),
            raw=command_raw,
        )
    return item_id
