# GitHub project issue

the workflow's GitHub repository context already names the normal repository target and the workflow needs project membership for one issue there.

Probe whether one GitHub issue is already attached to one GitHub Project and return the normalized membership item id plus the common project field values that Ordo reads from that membership. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- A workflow needs to know whether one issue is already in the target project before deciding to add it or update its project fields.
- Later logic needs one compact project-membership snapshot such as Status, Type, Priority, Iteration, Size, or Estimate for one issue in one project.

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
