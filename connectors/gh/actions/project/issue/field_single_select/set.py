"""gh.project.issue.field_single_select.set action."""

from __future__ import annotations

from connectors.gh.actions._shared import PROJECT_ISSUE_INVALIDATION
from connectors.gh.actions.project.issue._field_common import build_single_select_mutation, named_id, resolve_issue_and_field, run_field_update
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS
from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, action, fail, ok, preflight_observation


def info():
    return action(
        name="project.issue.field_single_select.set",
        inputs={**ISSUE_IDENTITY_INPUTS, "project_id": "string", "field": "string", "option": "string"},
        effects=("set one GitHub project issue single-select field by field name",),
        outputs={"issue_ref": "string", "project_id": "string", "item_id": "string", "field": "string", "option": "string", "changed": "boolean"},
        failure_modes=("issue_not_found", "project_not_found", "field_not_found", "field_kind_unsupported", "option_not_found", "field_update_blocked"),
        invalidates_observations=PROJECT_ISSUE_INVALIDATION,
        preflight_observations=(
            preflight_observation(probe="gh.project.issue", with_={"repository": "{repository}", "issue_number": "{issue_number}", "project_id": "{project_id}"}, fields=("exists",)),
            preflight_observation(probe="gh.project.field", with_={"project_id": "{project_id}", "field": "{field}"}, fields=("exists",)),
            preflight_observation(probe="gh.project.field.option", with_={"project_id": "{project_id}", "field": "{field}", "option": "{option}"}, fields=("exists",)),
        ),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    project_id = str(ctx.input("project_id"))
    field_name = str(ctx.input("field"))
    requested_option = str(ctx.input("option"))
    diagnostic_prefix = "action.gh_project_issue_field_single_select_set"
    resolved = resolve_issue_and_field(ctx, project_id=project_id, field_name=field_name, failure_code="field_update_blocked", diagnostic_prefix=diagnostic_prefix)
    if isinstance(resolved, OperationOutcome):
        return resolved
    issue_ref, issue_facts, project_field, item = resolved
    if project_field["field_kind"] != "single_select":
        return fail(
            code="field_kind_unsupported",
            summary=f"GitHub project field '{field_name}' is not a single-select field",
            diagnostics=(Diagnostic(code=f"{diagnostic_prefix}.field_kind_unsupported", level="error", message="GitHub project field kind is not supported", details={"reference": ctx.reference, "project_id": project_id, "field": field_name, "field_kind": project_field['field_kind']}),),
            raw={"project": project_field.get("raw", {})},
        )
    option_id = named_id(project_field.get("options"), requested_option)
    if option_id is None:
        return fail(
            code="option_not_found",
            summary=f"GitHub project field option '{requested_option}' was not found",
            diagnostics=(Diagnostic(code=f"{diagnostic_prefix}.option_not_found", level="error", message="GitHub project field option was not found", details={"reference": ctx.reference, "project_id": project_id, "field": field_name, "option": requested_option}),),
            raw={"project": project_field.get("raw", {})},
        )
    if item["value"] == requested_option:
        return ok(summary=f"GitHub project field '{field_name}' is already set", outputs={"issue_ref": issue_ref, "project_id": project_id, "item_id": item["item_id"], "field": field_name, "option": requested_option, "changed": False}, raw={"issue": issue_facts.get("raw", {}), "project": project_field.get("raw", {})})
    return run_field_update(
        ctx,
        mutation_argv=build_single_select_mutation(project_id=project_id, item_id=item["item_id"], field_id=project_field["field_id"], option_id=option_id),
        issue_ref=issue_ref,
        project_id=project_id,
        field_name=field_name,
        outputs={"issue_ref": issue_ref, "project_id": project_id, "field": field_name, "option": requested_option},
        issue_raw=issue_facts.get("raw", {}),
        project_raw=project_field.get("raw", {}),
        failure_code="field_update_blocked",
        diagnostic_prefix=diagnostic_prefix,
    )
