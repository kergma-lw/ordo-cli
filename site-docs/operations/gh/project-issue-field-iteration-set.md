# GitHub project issue field-iteration set

Move one issue that is already in a GitHub Project into a named iteration.

Set one iteration-valued GitHub Project field on one issue's Project item by field name and iteration title.

## Use when

- A workflow needs to move one project-backed issue into a named iteration such as Sprint 12.

## What to provide

- Provide the issue number, Project ID, visible iteration field name, and iteration title.
- Choose the project by owner and project number, retrieve its stable Project ID with the GitHub project view command, then confirm the project title with connector.gh.project. Use connector.gh.project.field to confirm the named iteration field and its available iterations before changing an issue.
- Use the workflow's GitHub repository context normally. Supply repository only when the issue belongs to a different repository.
- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.
- `project_id`: required.
- `field`: required.
- `iteration`: required.

## Result and boundary

- The result identifies the issue and its Project item, and reports whether the requested iteration changed. changed=false means the item was already in that iteration.
- The issue must already be in the Project and the named iteration must exist. Observe again before a decision that depends on the current iteration because another actor can change it.
- Usable result fact: `issue_ref`.
- Usable result fact: `project_id`.
- Usable result fact: `item_id`.
- Usable result fact: `field`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails. Required preflight facts must be established before the change is submitted.

## Do not use for

- Attaching the issue to the project in the first place; use connector.gh.project.issue.add when membership may still be missing.
- Updating numeric or single-select fields; use connector.gh.project.issue.field_number.set or connector.gh.project.issue.field_single_select.set for those different field kinds.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.project.issue`](project-issue.md): Parent issue-membership probe for reading current project field values before or after mutation
- [`connector.gh.project.field`](project-field.md): Sibling probe for confirming the project field exists and is iteration-backed before mutation
- [`connector.gh.project.issue.add`](project-issue-add.md): Sibling action for ensuring the issue is a project item before setting iteration
- [`connector.gh.project.issue.field_single_select.set`](project-issue-field-single-select-set.md): Sibling setter for selectable fields rather than iteration-backed fields

## Inspect next

- connector.gh.project.issue
- connector.gh.project.field
- connector.gh.project.issue.add

## Exact machine contract

Use `ordo-help operation gh.project.issue.field_iteration.set --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_issue_field_iteration_set_step

Move the project-backed issue into one named iteration after membership is already ensured.

```yaml
      - name: set-iteration
        uses: gh.project.issue.field_iteration.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Iteration"
          iteration: "Sprint 12"
```
