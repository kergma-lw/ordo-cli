"""gh.project.issue.field_number.set action."""

from __future__ import annotations

from connectors.gh.actions._shared import PROJECT_ISSUE_INVALIDATION
from connectors.gh.actions.project.issue._field_common import build_number_mutation, resolve_issue_and_field, run_field_update
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS
from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, action, fail, ok, preflight_observation
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub project issue field_number set',
  'goal': 'Set one numeric GitHub Project field on one issue that is already in that Project.',
  'summary': "Set one number-valued GitHub Project field on one issue's Project item by field name and numeric value.",
  'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to set one numeric field, such as Estimate, on a project-backed issue.']},
               {'heading': 'What to provide',
                'items': ['Provide the issue number, Project ID, visible field name, and numeric value.',
                          'Choose the project by its owner and project number using GitHub\'s published project guide, then obtain that project\'s stable ID with the GitHub project view command. Store that returned ID as workflow input and confirm the selected project title with connector.gh.project before changing an issue.',
                          'Use the workflow\'s GitHub repository context normally. Supply repository only when the issue belongs to a different repository.']},
              {'heading': 'Result and boundary',
               'items': ['The result identifies the issue and its Project item, and reports whether the requested value changed. changed=false means the item already held that value; changed=true means this action applied the requested value.',
                         'The issue must already be in the Project, and the named field must be numeric. Another actor can change the item after this action, so observe again before making a decision that depends on its current value.']},
               {'heading': 'Do not use for',
               'items': ['Writing selectable or iteration-backed project fields; use '
                         'connector.gh.project.issue.field_single_select.set or '
                         'connector.gh.project.issue.field_iteration.set for those different field kinds.',
                         'Reading the current field value without changing it; use connector.gh.project.issue when the '
                         'workflow only needs the observed membership snapshot.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.project.issue',
                               'summary': 'Parent issue-membership probe for inspecting current project field values '
                                          'before or after mutation'},
                              {'handle': 'connector.gh.project.field',
                               'summary': 'Sibling probe for confirming the target project field exists before '
                                          'mutation'},
                              {'handle': 'connector.gh.project.issue.field_single_select.set',
                               'summary': 'Sibling setter for selectable fields rather than numeric fields'},
                              {'handle': 'connector.gh.project.issue.field_iteration.set',
                               'summary': 'Sibling setter for iteration-backed fields rather than numeric fields'}]},
               {'heading': 'Examples',
                'items': ['After a project view has returned and connector.gh.project has confirmed inputs.project_id, set Estimate to 3 for issue 42.']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.project.issue',
                         'connector.gh.project.field',
                         'connector.gh.project.issue.field_single_select.set']}]})

def info():
    return action(
        name="project.issue.field_number.set",
        human=HUMAN,
        inputs={**ISSUE_IDENTITY_INPUTS, "project_id": "string", "field": "string", "value": "number"},
        effects=("set one GitHub project issue number field by field name",),
        outputs={"issue_ref": "string", "project_id": "string", "item_id": "string", "field": "string", "value": "number", "changed": "boolean"},
        failure_modes=("issue_not_found", "project_not_found", "field_not_found", "field_kind_unsupported", "field_value_invalid", "field_update_blocked"),
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
    value = ctx.input("value")
    diagnostic_prefix = "action.gh_project_issue_field_number_set"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fail(
            code="field_value_invalid",
            summary=f"GitHub project field '{field_name}' rejected the requested value",
            diagnostics=(Diagnostic(code=f"{diagnostic_prefix}.field_value_invalid", level="error", message="GitHub project field value was invalid", details={"reference": ctx.reference, "project_id": project_id, "field": field_name, "value": value}),),
        )
    resolved = resolve_issue_and_field(ctx, project_id=project_id, field_name=field_name, failure_code="field_update_blocked", diagnostic_prefix=diagnostic_prefix)
    if isinstance(resolved, OperationOutcome):
        return resolved
    issue_ref, issue_facts, project_field, item = resolved
    if project_field["field_kind"] != "number":
        return fail(
            code="field_kind_unsupported",
            summary=f"GitHub project field '{field_name}' is not a number field",
            diagnostics=(Diagnostic(code=f"{diagnostic_prefix}.field_kind_unsupported", level="error", message="GitHub project field kind is not supported", details={"reference": ctx.reference, "project_id": project_id, "field": field_name, "field_kind": project_field['field_kind']}),),
            raw={"project": project_field.get("raw", {})},
        )
    if item["value"] == value:
        return ok(summary=f"GitHub project field '{field_name}' is already set", outputs={"issue_ref": issue_ref, "project_id": project_id, "item_id": item["item_id"], "field": field_name, "value": value, "changed": False}, raw={"issue": issue_facts.get("raw", {}), "project": project_field.get("raw", {})})
    return run_field_update(
        ctx,
        mutation_argv=build_number_mutation(project_id=project_id, item_id=item["item_id"], field_id=project_field["field_id"], value=value),
        issue_ref=issue_ref,
        project_id=project_id,
        field_name=field_name,
        outputs={"issue_ref": issue_ref, "project_id": project_id, "field": field_name, "value": value},
        issue_raw=issue_facts.get("raw", {}),
        project_raw=project_field.get("raw", {}),
        failure_code="field_update_blocked",
        diagnostic_prefix=diagnostic_prefix,
    )
