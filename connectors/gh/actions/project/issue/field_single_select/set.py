"""gh.project.issue.field_single_select.set action."""

from __future__ import annotations

from connectors.gh.actions._shared import PROJECT_ISSUE_INVALIDATION
from connectors.gh.actions.project.issue._field_common import build_single_select_mutation, named_id, resolve_issue_and_field, run_field_update
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS
from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, action, fail, ok, preflight_observation
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'Set GitHub Project single-select field',
 'goal': 'Assign one visible Project choice to one issue in the workflow\'s normal GitHub repository.',
 'summary': "Set one single-select GitHub Project field on one issue's project item by field name and visible option "
            'name. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit '
            'repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to assign one selectable project value such as Status or Priority after '
                         'membership and field-option validation succeed.',
                          'The caller knows the human-facing option label and does not need to manage a stored '
                          'selection identity.']},
               {'heading': 'What to provide',
                'items': ['Provide the issue number, target Project ID, visible field name, and visible option label.',
                          'Choose the project by its owner and project number using GitHub\'s published project guide, then obtain that project\'s stable ID with the GitHub project view command. Store that returned ID as workflow input and confirm the selected project title with connector.gh.project before changing an issue.',
                          'Use the workflow\'s GitHub repository context normally; name another repository only as a '
                          'deliberate override.']},
               {'heading': 'Result and boundary',
                'items': ['Later steps can use the issue identity, Project item identity, selected field and option, and '
                           'whether the value actually changed. changed=false means the item already held that option; changed=true means this action applied it.',
                         'The issue must already be in the Project and the requested field and option must exist with the '
                           'right kind. A concurrent edit can make the returned changed state stale, so observe again before '
                          'a decision that depends on the current value.']},
              {'heading': 'Do not use for',
               'items': ['Writing iteration-backed or numeric project fields; use '
                         'connector.gh.project.issue.field_iteration.set or '
                         'connector.gh.project.issue.field_number.set for those different field kinds.',
                         'Checking whether the requested option exists without mutating anything; use '
                         'connector.gh.project.field.option when the workflow only needs a yes/no option probe.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.project.issue',
                               'summary': 'Parent issue-membership probe for reading current project field values '
                                          'before or after mutation'},
                              {'handle': 'connector.gh.project.field.option',
                               'summary': 'Sibling probe for validating one candidate selectable value before '
                                          'mutation'},
                              {'handle': 'connector.gh.project.issue.add',
                               'summary': 'Sibling action for ensuring the issue is a project item before setting a '
                                          'selectable field'},
                              {'handle': 'connector.gh.project.issue.field_number.set',
                               'summary': 'Sibling setter for numeric fields rather than selectable fields'}]},
               {'heading': 'Examples',
                'items': ['After a project view has returned and connector.gh.project has confirmed inputs.project_id, set Status to In review for issue 42.']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.project.field.option',
                         'connector.gh.project.issue',
                         'connector.gh.project.issue.add']}]})

def info():
    return action(
        name="project.issue.field_single_select.set",
        human=HUMAN,
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
