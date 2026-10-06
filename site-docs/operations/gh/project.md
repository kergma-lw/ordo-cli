# GitHub project

A workflow first needs to confirm that one GitHub Project exists before inspecting its fields, issue membership, or item collections.

Probe one GitHub Project by its stable project id and return a typed existence snapshot with the canonical id and title.

## Use when

- Later steps need the project's canonical title or want a narrow project-identity probe instead of jumping straight to field or membership surfaces.

## What to provide

- `project_id`: required.

## Result and boundary

- Usable result fact: `exists`.
- Usable result fact: `id`.
- Usable result fact: `title`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Inspecting one named field or its selectable values; use connector.gh.project.field or connector.gh.project.field.option for that narrower field story.
- Enumerating project items or checking whether one issue is already attached to the project; use connector.gh.project.items or connector.gh.project.issue for membership questions.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.gh`: Parent GitHub connector family for issue, pull-request, and project operations
- [`connector.gh.project.field`](project-field.md): Sibling probe for one named project field rather than the project identity itself
- [`connector.gh.project.items`](project-items.md): Sibling probe for project membership collections rather than top-level project identity
- [`connector.gh.project.issue`](project-issue.md): Sibling probe for whether one repository issue is already in the project

## Inspect next

- connector.gh.project.field
- connector.gh.project.items
- connector.gh.project.issue

## Exact machine contract

Use `ordo-help operation gh.project --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_probe_step

Confirm one GitHub Project identity before branching into field-level or membership-level project logic.

```yaml
      - name: Load project
        uses: gh.project
        with:
          project_id: inputs.project_id
        register: project
```
### gh_project_field_probe_flow

Inspect one project, one named field, and one candidate selectable option, then publish a compact readiness summary.

```yaml
version: 0
workflow: inspect-project-field-probes
inputs:
  project_id: {}
blocks:
   - guards: []
   - steps:
      # Inspect the project, Status field, and Done option.
      - name: Load project
        uses: gh.project
        with:
          project_id: inputs.project_id
        register: project
      - name: Load Status field
        uses: gh.project.field
        with:
          project_id: inputs.project_id
          field: "Status"
        register: status_field
      - name: Check Done option
        uses: gh.project.field.option
        with:
          project_id: inputs.project_id
          field: "Status"
          option: "Done"
        register: done_option
      - name: Publish summary
        publish:
          project_title: step.project.outputs.title
          field_kind: step.status_field.outputs.kind
          done_available: step.done_option.outputs.exists
```
