"""gh.project.issue probe."""

from __future__ import annotations

import json

from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="project.issue",
        inputs={**ISSUE_IDENTITY_INPUTS, "project_id": "string"},
        outputs={
            "exists": "boolean",
            "item_id": "string",
            "status": "string",
            "type": "string",
            "priority": "string",
            "iteration": "string",
            "size": "string",
            "estimate": "number",
        },
        failure_modes=("issue_not_found", "project_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    project_id = str(ctx.input("project_id"))
    identity = resolve_issue_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_project_issue")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    owner = identity.owner
    repo = identity.repo
    number = identity.issue_number

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
                    "projectItems(first:50){nodes{"
                    "id project{... on ProjectV2{id title}}"
                    "fieldValues(first:50){nodes{"
                    "... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{id name}}}"
                    "... on ProjectV2ItemFieldIterationValue{iterationId title startDate duration field{... on ProjectV2IterationField{id name}}}"
                    "... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2FieldCommon{id name}}}"
                    "}}}}}}}"
                ),
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
                "-F",
                f"number={number}",
            ],
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        stderr = str(outcome.raw.get("stderr", "")).lower()
        stdout = str(outcome.raw.get("stdout", "")).lower()
        text = f"{stderr}\n{stdout}"
        if outcome.status == "execution_error" and (
            "could not resolve to an issue" in text or "issue not found" in text or "not found" in text
        ):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="probe.gh_project_issue.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail(
            code="probe_failed",
            summary="GitHub project issue probe failed",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_project_issue.command_failed",
                    level="error",
                    message="GitHub project issue probe failed",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "project_id": project_id},
                ),
            ),
            raw=outcome.raw,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="probe_failed",
            summary="GitHub project issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_project_issue.invalid_json",
                    level="error",
                    message="GitHub project issue output was not valid JSON",
                    details={"reference": ctx.reference, "error": str(exc)},
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
                    code="probe.gh_project_issue.issue_not_found",
                    level="error",
                    message="GitHub issue was not found",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(issue_data, dict):
        return fail(
            code="probe_failed",
            summary="GitHub project issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_project_issue.invalid_shape",
                    level="error",
                    message="GitHub project issue output was not an object",
                    details={"reference": ctx.reference},
                ),
            ),
            raw=command.raw,
        )

    nodes = (((issue_data.get("projectItems") or {}).get("nodes")) or [])
    if not isinstance(nodes, list):
        return fail(
            code="probe_failed",
            summary="GitHub project item list was not valid",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_project_issue.invalid_project_items",
                    level="error",
                    message="GitHub project item list was not valid",
                    details={"reference": ctx.reference},
                ),
            ),
            raw=command.raw,
        )

    item = _match_project_item(nodes, project_id)
    if item is None:
        project_lookup = _lookup_project(ctx, project_id)
        if project_lookup is not None:
            return project_lookup
        return ok(
            summary="GitHub issue is not in the requested project",
            outputs={
                "exists": False,
                "item_id": None,
                "status": None,
                "type": None,
                "priority": None,
                "iteration": None,
                "size": None,
                "estimate": None,
            },
            raw=command.raw,
        )

    return ok(
        summary="GitHub project issue facts retrieved successfully",
        outputs={
            "exists": True,
            "item_id": item.get("id"),
            "status": item.get("status"),
            "type": item.get("type"),
            "priority": item.get("priority"),
            "iteration": item.get("iteration"),
            "size": item.get("size"),
            "estimate": item.get("estimate"),
        },
        raw=command.raw,
    )
def _match_project_item(nodes: list[object], project_id: str) -> dict[str, object] | None:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        project = node.get("project")
        if not isinstance(project, dict):
            continue
        candidate_project_id = project.get("id")
        if candidate_project_id != project_id:
            continue
        return {
            "id": node.get("id"),
            "status": _single_select_value(node, "Status"),
            "type": _single_select_value(node, "Type"),
            "priority": _single_select_value(node, "Priority"),
            "iteration": _iteration_value(node, "Iteration"),
            "size": _single_select_value(node, "Size"),
            "estimate": _number_value(node, "Estimate"),
        }
    return None


def _field_nodes(node: dict[str, object]) -> list[object]:
    return (((node.get("fieldValues") or {}).get("nodes")) or [])  # type: ignore[union-attr]


def _single_select_value(node: dict[str, object], field_name: str) -> object:
    for field_value in _field_nodes(node):
        if not isinstance(field_value, dict):
            continue
        field = field_value.get("field")
        if not isinstance(field, dict):
            continue
        if field.get("name") == field_name:
            return field_value.get("name")
    return None


def _iteration_value(node: dict[str, object], field_name: str) -> object:
    for field_value in _field_nodes(node):
        if not isinstance(field_value, dict):
            continue
        field = field_value.get("field")
        if not isinstance(field, dict):
            continue
        if field.get("name") == field_name:
            return field_value.get("title")
    return None


def _number_value(node: dict[str, object], field_name: str) -> object:
    for field_value in _field_nodes(node):
        if not isinstance(field_value, dict):
            continue
        field = field_value.get("field")
        if not isinstance(field, dict):
            continue
        if field.get("name") == field_name:
            return field_value.get("number")
    return None


def _lookup_project(ctx: OperationContext, project_id: str) -> OperationOutcome | None:
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
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError:
        return None
    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError:
        return None
    project = ((payload.get("data") or {}).get("node"))
    if project is None:
        return fail(
            code="project_not_found",
            summary="GitHub project was not found",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_project_issue.project_not_found",
                    level="error",
                    message="GitHub project was not found",
                    details={"reference": ctx.reference, "project_id": project_id},
                ),
            ),
            raw=command.raw,
        )
    return None
