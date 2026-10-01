# GitHub project issue

the workflow's GitHub repository context already names the normal repository target and the workflow needs project membership for one issue there.

Probe whether one GitHub issue is already attached to one GitHub Project and return the normalized membership item id, common project field values, and arbitrary named scalar project fields in custom_fields. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- A workflow needs to know whether one issue is already in the target project before deciding to add it or update its project fields.
- Later logic needs one compact project-membership snapshot such as Status, Type, Priority, Iteration, Size, Estimate, or a custom field for one issue in one project.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.
- `project_id`: required.

## Result and boundary

- Usable result fact: `exists`.
- Usable result fact: `item_id`.
- Usable result fact: `status`.
- Usable result fact: `type`.
- Usable result fact: `priority`.
- Usable result fact: `iteration`.
- Usable result fact: `size`.
- Usable result fact: `estimate`.
- Usable result fact: `custom_fields`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Scanning many project items or filtering project membership collections; use connector.gh.project.items or connector.gh.project.items.details for collection-shaped project inspection.
- Adding the issue to the project or mutating project field values; use connector.gh.project.issue.add or connector.gh.project.issue.field_single_select.set, connector.gh.project.issue.field_number.set, or connector.gh.project.issue.field_iteration.set for those effectful changes.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.project`](project.md): Parent project probe for confirming the target project identity before issue-membership inspection
- [`connector.gh.project.issue.add`](project-issue-add.md): Sibling action for attaching the issue to the project when this probe reports exists=false
- [`connector.gh.project.items`](project-items.md): Sibling probe for project-wide membership scans instead of one issue-specific membership lookup
- [`connector.gh.project.issue.field_single_select.set`](project-issue-field-single-select-set.md): Sibling action for mutating one project field after membership inspection confirms the target issue context

## Read project fields

- The normalized status, type, priority, iteration, size, and estimate outputs are compatibility shortcuts for project fields with those exact names.
- Use custom_fields to read arbitrary named scalar project fields. Look up the exact field name, including spaces and case, rather than using dotted access. Each name maps to a list so duplicate project field names remain visible. For example, use step.membership.outputs.custom_fields | lookup("Work type") | first | field("value") to read the first Work type value.
- Each custom_fields entry includes field_id, kind, and value. Single-select, iteration, text, and date values are strings; number values are numbers. Unset, composite, and unsupported field values are omitted.
- The type output remains the normalized shortcut for the field named Type. A project field also named Type is independently available through custom_fields.

## Filter by a custom single-select field

- To decide whether a project item has a custom single-select value, use gh.project.items with filters [{field: "Work type", value: "Task"}] and a content_refs value for the issue, then guard on the matching item count. Work type is an illustrative field name, not a built-in field.

## Inspect next

- connector.gh.project.issue.add
- connector.gh.project.issue.field_single_select.set
- connector.gh.project.items

## Exact machine contract

Use `ordo-help operation gh.project.issue --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_issue_probe_step

Inspect whether one issue is already attached to the target GitHub Project before deciding whether to add it or mutate its fields.

```yaml
      - name: load-membership
        uses: gh.project.issue
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
        register: membership
```
### gh_project_issue_membership_flow

Probe one issue's project membership, attach it if needed, then set representative single-select, number, and iteration fields through typed project issue surfaces.

```yaml
version: 0
workflow: prepare-project-issue-membership
inputs:
  repository: {}
  issue_number: {}
  project_id: {}
blocks:
  - guards: []
  - steps:
      - name: load-membership
        uses: gh.project.issue
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
        register: membership
      - name: add-to-project
        if: not step.membership.outputs.exists
        uses: gh.project.issue.add
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
        register: membership_add
      - name: set-estimate
        uses: gh.project.issue.field_number.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Estimate"
          value: 3
      - name: set-iteration
        uses: gh.project.issue.field_iteration.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Iteration"
          iteration: "Sprint 12"
      - name: set-status
        uses: gh.project.issue.field_single_select.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Status"
          option: "In review"
```
