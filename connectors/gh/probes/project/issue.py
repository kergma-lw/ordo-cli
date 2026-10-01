"""gh.project.issue probe."""

from __future__ import annotations

import json

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub project issue',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and the workflow needs project '
         'membership for one issue there.',
 'summary': 'Probe whether one GitHub issue is already attached to one GitHub Project and return the normalized '
            'membership item id plus the common project field values that Ordo reads from that membership. Prefer '
            'connector_contexts.gh.repository as the normal repository target and use an explicit repository argument '
            'only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and the workflow '
                         'needs project membership for one issue there.',
                         'A workflow needs to know whether one issue is already in the target project before deciding '
                         'to add it or update its project fields.',
                         'Later logic needs one compact project-membership snapshot such as Status, Type, Priority, '
                         'Iteration, Size, or Estimate for one issue in one project.']},
              {'heading': 'Do not use for',
               'items': ['Scanning many project items or filtering project membership collections; use '
                         'connector.gh.project.items or connector.gh.project.items.details for collection-shaped '
                         'project inspection.',
                         'Adding the issue to the project or mutating project field values; use '
                          'connector.gh.project.issue.add or connector.gh.project.issue.field_single_select.set, '
                          'connector.gh.project.issue.field_number.set, or connector.gh.project.issue.field_iteration.set '
                          'for those effectful changes.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.project',
                               'summary': 'Parent project probe for confirming the target project identity before '
                                          'issue-membership inspection'},
                              {'handle': 'connector.gh.project.issue.add',
                               'summary': 'Sibling action for attaching the issue to the project when this probe '
                                          'reports exists=false'},
                              {'handle': 'connector.gh.project.items',
                               'summary': 'Sibling probe for project-wide membership scans instead of one '
                                          'issue-specific membership lookup'},
                              {'handle': 'connector.gh.project.issue.field_single_select.set',
                               'summary': 'Sibling action for mutating one project field after membership inspection '
                                          'confirms the target issue context'}]},
              {'heading': 'Examples',
               'items': ['gh.project.issue with inputs {"issue_number": 42, "project_id": "PVT_kwDOExample"}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.project.issue.add',
                         'connector.gh.project.issue.field_single_select.set',
                         'connector.gh.project.items']}]})

def info():
    return probe(
        name="project.issue",
        human=HUMAN,
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
        text = command_text(outcome.raw)
        if outcome.status == "execution_error" and text_mentions_not_found(text, "could not resolve to an issue", "issue not found"):
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
        return fail_github_command(
            ctx,
            code="probe_failed",
            summary="GitHub project issue probe failed",
            raw=outcome.raw,
            diagnostic_code="probe.gh_project_issue.command_failed",
            details={"issue_ref": issue_ref, "project_id": project_id},
            message="GitHub project issue probe failed",
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
