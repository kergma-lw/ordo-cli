# Set GitHub Project single-select field

Assign one visible Project choice to one issue in the workflow's normal GitHub repository.

Set one single-select GitHub Project field on one issue's project item by field name and visible option name. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- A workflow needs to assign one selectable project value such as Status or Priority after membership and field-option validation succeed.
- The caller knows the human-facing option label and does not need to manage a stored selection identity.

## What to provide

- Provide the issue number, target Project ID, visible field name, and visible option label.
- Choose the project by its owner and project number using GitHub's published project guide, then obtain that project's stable ID with the GitHub project view command. Store that returned ID as workflow input and confirm the selected project title with connector.gh.project before changing an issue.
- Use the workflow's GitHub repository context normally; name another repository only as a deliberate override.
- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.
- `project_id`: required.
- `field`: required.
- `option`: required.

## Result and boundary

- Later steps can use the issue identity, Project item identity, selected field and option, and whether the value actually changed. changed=false means the item already held that option; changed=true means this action applied it.
- The issue must already be in the Project and the requested field and option must exist with the right kind. A concurrent edit can make the returned changed state stale, so observe again before a decision that depends on the current value.
- Usable result fact: `issue_ref`.
- Usable result fact: `project_id`.
- Usable result fact: `item_id`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails. Required preflight facts must be established before the change is submitted.

## Do not use for

- Writing iteration-backed or numeric project fields; use connector.gh.project.issue.field_iteration.set or connector.gh.project.issue.field_number.set for those different field kinds.
- Checking whether the requested option exists without mutating anything; use connector.gh.project.field.option when the workflow only needs a yes/no option probe.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.project.issue`](project-issue.md): Parent issue-membership probe for reading current project field values before or after mutation
- [`connector.gh.project.field.option`](project-field-option.md): Sibling probe for validating one candidate selectable value before mutation
- [`connector.gh.project.issue.add`](project-issue-add.md): Sibling action for ensuring the issue is a project item before setting a selectable field
- [`connector.gh.project.issue.field_number.set`](project-issue-field-number-set.md): Sibling setter for numeric fields rather than selectable fields

## Inspect next

- connector.gh.project.field.option
- connector.gh.project.issue
- connector.gh.project.issue.add

## Exact machine contract

Use `ordo-help operation gh.project.issue.field_single_select.set --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_issue_field_single_select_set_step

Set one selectable project field such as Status by its visible option name after membership is ensured.

```yaml
      - name: set-status
        uses: gh.project.issue.field_single_select.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Status"
          option: "In review"
```
