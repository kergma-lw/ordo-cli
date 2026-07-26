"""gh.project.issue.field_iteration.set action."""

from __future__ import annotations

from connectors.gh.actions._shared import PROJECT_ISSUE_INVALIDATION
from connectors.gh.actions.project.issue._field_common import build_iteration_mutation, named_id, resolve_issue_and_field, run_field_update
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS
from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, action, fail, ok, preflight_observation


def info():
    return action(
        name="project.issue.field_iteration.set",
        inputs={**ISSUE_IDENTITY_INPUTS, "project_id": "string", "field": "string", "iteration": "string"},
        effects=("set one GitHub project issue iteration field by field name",),
        outputs={"issue_ref": "string", "project_id": "string", "item_id": "string", "field": "string", "iteration": "string", "changed": "boolean"},
        failure_modes=("issue_not_found", "project_not_found", "field_not_found", "field_kind_unsupported", "iteration_not_found", "field_update_blocked"),
        invalidates_observations=PROJECT_ISSUE_INVALIDATION,
        preflight_observations=(
            preflight_observation(probe="gh.project.issue", with_={"repository": "{repository}", "issue_number": "{issue_number}", "project_id": "{project_id}"}, fields=("exists",)),
            preflight_observation(probe="gh.project.field", with_={"project_id": "{project_id}", "field": "{field}"}, fields=("exists",)),
        ),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    project_id = str(ctx.input("project_id"))
    field_name = str(ctx.input("field"))
    iteration = str(ctx.input("iteration"))
    diagnostic_prefix = "action.gh_project_issue_field_iteration_set"
    resolved = resolve_issue_and_field(ctx, project_id=project_id, field_name=field_name, failure_code="field_update_blocked", diagnostic_prefix=diagnostic_prefix)
    if isinstance(resolved, OperationOutcome):
        return resolved
    issue_ref, issue_facts, project_field, item = resolved
    if project_field["field_kind"] != "iteration":
        return fail(
            code="field_kind_unsupported",
            summary=f"GitHub project field '{field_name}' is not an iteration field",
            diagnostics=(Diagnostic(code=f"{diagnostic_prefix}.field_kind_unsupported", level="error", message="GitHub project field kind is not supported", details={"reference": ctx.reference, "project_id": project_id, "field": field_name, "field_kind": project_field['field_kind']}),),
            raw={"project": project_field.get("raw", {})},
        )
    iteration_id = named_id(project_field.get("iterations"), iteration, key="title")
    if iteration_id is None:
        return fail(
            code="iteration_not_found",
            summary=f"GitHub project iteration '{iteration}' was not found",
            diagnostics=(Diagnostic(code=f"{diagnostic_prefix}.iteration_not_found", level="error", message="GitHub project iteration was not found", details={"reference": ctx.reference, "project_id": project_id, "field": field_name, "iteration": iteration}),),
            raw={"project": project_field.get("raw", {})},
        )
    if item["value"] == iteration:
        return ok(summary=f"GitHub project field '{field_name}' is already set", outputs={"issue_ref": issue_ref, "project_id": project_id, "item_id": item["item_id"], "field": field_name, "iteration": iteration, "changed": False}, raw={"issue": issue_facts.get("raw", {}), "project": project_field.get("raw", {})})
    return run_field_update(
        ctx,
        mutation_argv=build_iteration_mutation(project_id=project_id, item_id=item["item_id"], field_id=project_field["field_id"], iteration_id=iteration_id),
        issue_ref=issue_ref,
        project_id=project_id,
        field_name=field_name,
        outputs={"issue_ref": issue_ref, "project_id": project_id, "field": field_name, "iteration": iteration},
        issue_raw=issue_facts.get("raw", {}),
        project_raw=project_field.get("raw", {}),
        failure_code="field_update_blocked",
        diagnostic_prefix=diagnostic_prefix,
    )
