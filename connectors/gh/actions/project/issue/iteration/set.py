"""gh.project.issue.iteration.set action."""

from __future__ import annotations

import json
import re

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok

_ISSUE_REF_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<repo>[^#]+)#(?P<number>\d+)$")


def info():
    return action(
        name="project.issue.iteration.set",
        inputs={"issue_ref": "string", "project_id": "string", "iteration": "string"},
        effects=("set GitHub project issue iteration",),
        outputs={"issue_ref": "string", "project_id": "string", "item_id": "string", "iteration": "string", "changed": "boolean"},
        failure_modes=("issue_not_found", "project_not_found", "iteration_not_found", "iteration_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    issue_ref = str(ctx.input("issue_ref"))
    project_id = str(ctx.input("project_id"))
    requested_iteration = str(ctx.input("iteration"))

    parsed = _parse_issue_ref(issue_ref)
    if parsed is None:
        return fail(
            code="iteration_blocked",
            summary="GitHub issue reference must use OWNER/REPO#N format",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.invalid_issue_ref",
                    level="error",
                    message="GitHub issue reference must use OWNER/REPO#N format",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
        )

    owner, repo, number = parsed
    issue_facts = _load_issue_membership(ctx, issue_ref=issue_ref, owner=owner, repo=repo, number=number)
    if isinstance(issue_facts, OperationOutcome):
        return issue_facts

    item = _match_project_item(issue_facts.get("project_items"), project_id)
    if item is None:
        project_lookup = _lookup_project_iteration_field(ctx, project_id=project_id)
        if isinstance(project_lookup, OperationOutcome):
            return project_lookup
        return fail(
            code="iteration_blocked",
            summary="GitHub issue is not in the requested project",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.item_not_found",
                    level="error",
                    message="GitHub issue is not in the requested project",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id},
                ),
            ),
            raw={"issue": issue_facts.get("raw", {}), "project": project_lookup.get("raw", {})},
        )

    item_id = item["item_id"]
    current_iteration = item["iteration"]
    if current_iteration == requested_iteration:
        return ok(
            summary="GitHub project issue iteration is already set",
            outputs={
                "issue_ref": issue_ref,
                "project_id": project_id,
                "item_id": item_id,
                "iteration": requested_iteration,
                "changed": False,
            },
            raw={"issue": issue_facts.get("raw", {})},
        )

    project_lookup = _lookup_project_iteration_field(ctx, project_id=project_id)
    if isinstance(project_lookup, OperationOutcome):
        return project_lookup
    iteration_id = _iteration_id(project_lookup.get("iterations"), requested_iteration)
    if iteration_id is None:
        return fail(
            code="iteration_not_found",
            summary=f"GitHub project iteration '{requested_iteration}' was not found",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.iteration_not_found",
                    level="error",
                    message="GitHub project iteration was not found",
                    details={"reference": ctx.reference, "project_id": project_id, "iteration": requested_iteration},
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
                "mutation($project:ID!,$item:ID!,$field:ID!,$iteration:String!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{iterationId:$iteration}}){projectV2Item{id}}}",
                "-f",
                f"project={project_id}",
                "-f",
                f"item={item_id}",
                "-f",
                f"field={project_lookup['field_id']}",
                "-f",
                f"iteration={iteration_id}",
            ],
            failures={"os_error": "iteration_blocked", "nonzero": "iteration_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="iteration_blocked",
            summary="Updating GitHub project issue iteration failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.command_failed",
                    level="error",
                    message="Updating GitHub project issue iteration failed",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "iteration": requested_iteration},
                ),
            ),
            raw=exc.outcome.raw,
        )

    updated_item_id = _extract_updated_item_id(
        ctx,
        issue_ref=issue_ref,
        project_id=project_id,
        requested_iteration=requested_iteration,
        command_stdout=command.stdout,
        command_raw=command.raw,
    )
    if isinstance(updated_item_id, OperationOutcome):
        return updated_item_id

    return ok(
        summary="Updated GitHub project issue iteration",
        outputs={
            "issue_ref": issue_ref,
            "project_id": project_id,
            "item_id": updated_item_id,
            "iteration": requested_iteration,
            "changed": True,
        },
        raw={"issue": issue_facts.get("raw", {}), "project": project_lookup.get("raw", {}), "update": command.raw},
    )


def _parse_issue_ref(value: str) -> tuple[str, str, int] | None:
    match = _ISSUE_REF_RE.match(value)
    if match is None:
        return None
    return match.group("owner"), match.group("repo"), int(match.group("number"))


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
                    "query($owner:String!,$repo:String!,$number:Int!){"
                    "repository(owner:$owner,name:$repo){"
                    "issue(number:$number){"
                    "projectItems(first:50){nodes{id project{... on ProjectV2{id}} fieldValues(first:50){nodes{... on ProjectV2ItemFieldIterationValue{title field{... on ProjectV2IterationField{name}}}}}}"
                    "}}}"
                ),
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
                "-F",
                f"number={number}",
            ],
            failures={"os_error": "iteration_blocked", "nonzero": "iteration_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if outcome.status == "iteration_blocked" and (
            "could not resolve to an issue" in text or "issue not found" in text or "not found" in text
        ):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_project_issue_iteration_set.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail(
            code="iteration_blocked",
            summary="Inspecting GitHub project issue membership failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.inspect_failed",
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
            code="iteration_blocked",
            summary="GitHub project issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.invalid_json",
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
                    code="action.gh_project_issue_iteration_set.issue_not_found",
                    level="error",
                    message="GitHub issue was not found",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )
    if not isinstance(issue_data, dict):
        return fail(
            code="iteration_blocked",
            summary="GitHub project issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.invalid_shape",
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
        iteration = None
        field_values = (((node.get("fieldValues") or {}).get("nodes")) or [])
        if isinstance(field_values, list):
            for field_value in field_values:
                if not isinstance(field_value, dict):
                    continue
                field = field_value.get("field")
                if not isinstance(field, dict) or field.get("name") != "Iteration":
                    continue
                title = field_value.get("title")
                iteration = title if isinstance(title, str) else None
                break
        return {"item_id": item_id, "iteration": iteration}
    return None


def _lookup_project_iteration_field(ctx: OperationContext, *, project_id: str) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                "query($id:ID!){node(id:$id){... on ProjectV2{id title fields(first:50){nodes{... on ProjectV2IterationField{id name configuration{iterations{... on ProjectV2IterationFieldIteration{id title startDate duration}}}}}}}}}",
                "-f",
                f"id={project_id}",
            ],
            failures={"os_error": "iteration_blocked", "nonzero": "iteration_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="iteration_blocked",
            summary="Inspecting GitHub project failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.project_lookup_failed",
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
            code="iteration_blocked",
            summary="GitHub project output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.project_invalid_json",
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
                    code="action.gh_project_issue_iteration_set.project_not_found",
                    level="error",
                    message="GitHub project was not found",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )
    if not isinstance(project, dict):
        return fail(
            code="iteration_blocked",
            summary="GitHub project output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.project_invalid_shape",
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
            code="iteration_not_found",
            summary="GitHub project iteration field was not found",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.field_missing",
                    level="error",
                    message="GitHub project iteration field was not found",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )

    for field in field_nodes:
        if not isinstance(field, dict):
            continue
        if field.get("name") != "Iteration":
            continue
        field_id = field.get("id")
        if not isinstance(field_id, str) or not field_id.strip():
            break
        configuration = field.get("configuration") or {}
        iterations = configuration.get("iterations") if isinstance(configuration, dict) else []
        return {"field_id": field_id, "iterations": iterations or [], "raw": command.raw}

    return fail(
        code="iteration_not_found",
        summary="GitHub project iteration field was not found",
        diagnostics=(
            Diagnostic(
                code="action.gh_project_issue_iteration_set.field_missing",
                level="error",
                message="GitHub project iteration field was not found",
                details={"reference": ctx.reference, "project_id": project_id},
            ),
        ),
        raw=command.raw,
    )


def _iteration_id(iterations: object, requested_iteration: str) -> str | None:
    if not isinstance(iterations, list):
        return None
    for iteration in iterations:
        if not isinstance(iteration, dict):
            continue
        if iteration.get("title") != requested_iteration:
            continue
        iteration_id = iteration.get("id")
        if isinstance(iteration_id, str) and iteration_id.strip():
            return iteration_id
    return None


def _extract_updated_item_id(
    ctx: OperationContext,
    *,
    issue_ref: str,
    project_id: str,
    requested_iteration: str,
    command_stdout: str,
    command_raw: dict[str, object],
) -> str | OperationOutcome:
    try:
        payload = json.loads(command_stdout) if command_stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="iteration_blocked",
            summary="GitHub project iteration update output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.update_invalid_json",
                    level="error",
                    message="GitHub project iteration update output was not valid JSON",
                    details={
                        "reference": ctx.reference,
                        "issue_ref": issue_ref,
                        "project_id": project_id,
                        "iteration": requested_iteration,
                        "error": str(exc),
                    },
                ),
            ),
            raw=command_raw,
        )

    item = (((payload.get("data") or {}).get("updateProjectV2ItemFieldValue") or {}).get("projectV2Item"))
    if not isinstance(item, dict):
        return fail(
            code="iteration_blocked",
            summary="GitHub project iteration update output was missing the updated item",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.item_missing",
                    level="error",
                    message="GitHub project iteration update output was missing the updated item",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "iteration": requested_iteration},
                ),
            ),
            raw=command_raw,
        )
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        return fail(
            code="iteration_blocked",
            summary="GitHub project iteration update output did not include a usable item id",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_iteration_set.item_id_missing",
                    level="error",
                    message="GitHub project iteration update output did not include a usable item id",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "iteration": requested_iteration},
                ),
            ),
            raw=command_raw,
        )
    return item_id
