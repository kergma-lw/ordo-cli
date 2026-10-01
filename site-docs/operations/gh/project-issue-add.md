# GitHub project issue add

the workflow's GitHub repository context already names the normal repository target and the workflow needs to ensure one issue there becomes a project item.

Add one GitHub issue to one GitHub Project and return the project item id, while staying idempotent when the issue is already attached. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- A workflow has one concrete issue and one target project and needs to ensure that the issue becomes a project item before later project-field updates.
- The workflow wants one typed membership-creation result instead of shelling out to ad hoc gh project mutations.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.
- `project_id`: required.

## Result and boundary

- Usable result fact: `issue_ref`.
- Usable result fact: `project_id`.
- Usable result fact: `item_id`.
- Usable result fact: `added`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails.

## Do not use for

- Checking membership without changing anything; use connector.gh.project.issue when the real question is whether the issue is already in the project.
- Updating Status, Estimate, Iteration, or another project-backed field after membership exists; use connector.gh.project.issue.field_single_select.set, connector.gh.project.issue.field_number.set, or connector.gh.project.issue.field_iteration.set for those follow-up mutations.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.project.issue`](project-issue.md): Sibling probe for membership inspection before or after this action
- [`connector.gh.project.issue.field_single_select.set`](project-issue-field-single-select-set.md): Follow-up action for setting one selectable project field after membership is ensured
- [`connector.gh.project.issue.field_number.set`](project-issue-field-number-set.md): Follow-up action for setting one numeric project field after membership is ensured
- [`connector.gh.project.items`](project-items.md): Project-wide collection probe when the workflow needs many project items rather than attaching one issue

## Inspect next

- connector.gh.project.issue
- connector.gh.project.issue.field_single_select.set
- connector.gh.project.issue.field_number.set

## Exact machine contract

Use `ordo-help operation gh.project.issue.add --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_issue_add_step

Attach the issue to the target GitHub Project only when the earlier membership probe reported exists=false.

```yaml
      - name: add-to-project
        if: not step.membership.outputs.exists
        uses: gh.project.issue.add
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
        register: membership_add
```
