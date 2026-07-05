"""gh.project.issue.add action."""

from __future__ import annotations

import json

from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok


def info():
    return action(
        name="project.issue.add",
        inputs={**ISSUE_IDENTITY_INPUTS, "project_id": "string"},
        effects=("add GitHub issue to project",),
        outputs={"issue_ref": "string", "project_id": "string", "item_id": "string", "added": "boolean"},
        failure_modes=("issue_not_found", "project_not_found", "add_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    project_id = str(ctx.input("project_id"))
    identity = resolve_issue_identity(ctx, failure_code="add_blocked", diagnostic_prefix="action.gh_project_issue_add")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    owner = identity.owner
    repo = identity.repo
    number = identity.issue_number
    issue_facts = _load_issue_facts(ctx, issue_ref=issue_ref, owner=owner, repo=repo, number=number)
    if isinstance(issue_facts, OperationOutcome):
        return issue_facts

    existing_item_id = _match_project_item_id(issue_facts.get("project_items"), project_id)
    if existing_item_id is not None:
        return ok(
            summary="GitHub issue is already in the requested project",
            outputs={"issue_ref": issue_ref, "project_id": project_id, "item_id": existing_item_id, "added": False},
            raw={"issue": issue_facts.get("raw", {})},
        )

    project_lookup = _lookup_project(ctx, project_id=project_id)
    if isinstance(project_lookup, OperationOutcome):
        return project_lookup

    issue_node_id = issue_facts.get("issue_id")
    if not isinstance(issue_node_id, str) or not issue_node_id.strip():
        return fail(
            code="add_blocked",
            summary="GitHub issue output did not include a usable node id",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.issue_id_missing",
                    level="error",
                    message="GitHub issue output did not include a usable node id",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw={"issue": issue_facts.get("raw", {})},
        )

    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                "mutation($project:ID!,$content:ID!){addProjectV2ItemById(input:{projectId:$project,contentId:$content}){item{id}}}",
                "-f",
                f"project={project_id}",
                "-f",
                f"content={issue_node_id}",
            ],
            failures={"os_error": "add_blocked", "nonzero": "add_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="add_blocked",
            summary="Adding GitHub issue to project failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.command_failed",
                    level="error",
                    message="Adding GitHub issue to project failed",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id},
                ),
            ),
            raw=exc.outcome.raw,
        )

    item_id = _extract_item_id(ctx, issue_ref=issue_ref, project_id=project_id, command_stdout=command.stdout, command_raw=command.raw)
    if isinstance(item_id, OperationOutcome):
        return item_id

    return ok(
        summary="Added GitHub issue to project",
        outputs={"issue_ref": issue_ref, "project_id": project_id, "item_id": item_id, "added": True},
        raw={"issue": issue_facts.get("raw", {}), "project": project_lookup, "add": command.raw},
    )
def _load_issue_facts(
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
                    "id projectItems(first:50){nodes{id project{... on ProjectV2{id}}}}"
                    "}}}"
                ),
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
                "-F",
                f"number={number}",
            ],
            failures={"os_error": "add_blocked", "nonzero": "add_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if outcome.status == "add_blocked" and (
            "could not resolve to an issue" in text or "issue not found" in text or "not found" in text
        ):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_project_issue_add.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail(
            code="add_blocked",
            summary="Inspecting GitHub project issue membership failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.inspect_failed",
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
            code="add_blocked",
            summary="GitHub project issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.invalid_json",
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
                    code="action.gh_project_issue_add.issue_not_found",
                    level="error",
                    message="GitHub issue was not found",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )
    if not isinstance(issue_data, dict):
        return fail(
            code="add_blocked",
            summary="GitHub project issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.invalid_shape",
                    level="error",
                    message="GitHub project issue output was not an object",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    return {
        "issue_id": issue_data.get("id"),
        "project_items": (((issue_data.get("projectItems") or {}).get("nodes")) or []),
        "raw": command.raw,
    }


def _match_project_item_id(nodes: object, project_id: str) -> str | None:
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if not isinstance(node, dict):
            continue
        project = node.get("project")
        if not isinstance(project, dict):
            continue
        if project.get("id") != project_id:
            continue
        item_id = node.get("id")
        if isinstance(item_id, str) and item_id.strip():
            return item_id
    return None


def _lookup_project(ctx: OperationContext, *, project_id: str) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                "query=query($id:ID!){node(id:$id){... on ProjectV2{id title}}}",
                "-f",
                f"id={project_id}",
            ],
            failures={"os_error": "add_blocked", "nonzero": "add_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail(
            code="add_blocked",
            summary="Inspecting GitHub project failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.project_lookup_failed",
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
            code="add_blocked",
            summary="GitHub project output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.project_invalid_json",
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
                    code="action.gh_project_issue_add.project_not_found",
                    level="error",
                    message="GitHub project was not found",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )
    if not isinstance(project, dict):
        return fail(
            code="add_blocked",
            summary="GitHub project output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.project_invalid_shape",
                    level="error",
                    message="GitHub project output was not an object",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )
    return {"raw": command.raw, "project": project}


def _extract_item_id(
    ctx: OperationContext, *, issue_ref: str, project_id: str, command_stdout: str, command_raw: dict[str, object]
) -> str | OperationOutcome:
    try:
        payload = json.loads(command_stdout) if command_stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="add_blocked",
            summary="GitHub project add output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.add_invalid_json",
                    level="error",
                    message="GitHub project add output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id, "error": str(exc)},
                ),
            ),
            raw=command_raw,
        )

    item = (((payload.get("data") or {}).get("addProjectV2ItemById") or {}).get("item"))
    if not isinstance(item, dict):
        return fail(
            code="add_blocked",
            summary="GitHub project add output was missing the new item",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.item_missing",
                    level="error",
                    message="GitHub project add output was missing the new item",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id},
                ),
            ),
            raw=command_raw,
        )
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        return fail(
            code="add_blocked",
            summary="GitHub project add output did not include a usable item id",
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_add.item_id_missing",
                    level="error",
                    message="GitHub project add output did not include a usable item id",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id},
                ),
            ),
            raw=command_raw,
        )
    return item_id
