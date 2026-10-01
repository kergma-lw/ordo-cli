# GitHub project issue field-number set

Set one numeric GitHub Project field on one issue that is already in that Project.

Set one number-valued GitHub Project field on one issue's Project item by field name and numeric value.

## Use when

- A workflow needs to set one numeric field, such as Estimate, on a project-backed issue.

## What to provide

- Provide the issue number, Project ID, visible field name, and numeric value.
- Choose the project by its owner and project number using GitHub's published project guide, then obtain that project's stable ID with the GitHub project view command. Store that returned ID as workflow input and confirm the selected project title with connector.gh.project before changing an issue.
- Use the workflow's GitHub repository context normally. Supply repository only when the issue belongs to a different repository.
- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.
- `project_id`: required.
- `field`: required.
- `value`: required.

## Result and boundary

- The result identifies the issue and its Project item, and reports whether the requested value changed. changed=false means the item already held that value; changed=true means this action applied the requested value.
- The issue must already be in the Project, and the named field must be numeric. Another actor can change the item after this action, so observe again before making a decision that depends on its current value.
- Usable result fact: `issue_ref`.
- Usable result fact: `project_id`.
- Usable result fact: `item_id`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails. Required preflight facts must be established before the change is submitted.

## Do not use for

- Writing selectable or iteration-backed project fields; use connector.gh.project.issue.field_single_select.set or connector.gh.project.issue.field_iteration.set for those different field kinds.
- Reading the current field value without changing it; use connector.gh.project.issue when the workflow only needs the observed membership snapshot.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.project.issue`](project-issue.md): Parent issue-membership probe for inspecting current project field values before or after mutation
- [`connector.gh.project.field`](project-field.md): Sibling probe for confirming the target project field exists before mutation
- [`connector.gh.project.issue.field_single_select.set`](project-issue-field-single-select-set.md): Sibling setter for selectable fields rather than numeric fields
- [`connector.gh.project.issue.field_iteration.set`](project-issue-field-iteration-set.md): Sibling setter for iteration-backed fields rather than numeric fields

## Inspect next

- connector.gh.project.issue
- connector.gh.project.field
- connector.gh.project.issue.field_single_select.set

## Exact machine contract

Use `ordo-help operation gh.project.issue.field_number.set --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_issue_field_number_set_step

Write one numeric project field such as Estimate after the issue is attached to the project.

```yaml
      - name: set-estimate
        uses: gh.project.issue.field_number.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Estimate"
          value: 3
```
