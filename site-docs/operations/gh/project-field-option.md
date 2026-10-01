# GitHub project field option

A workflow needs one explicit yes/no check that a candidate value such as Done is valid before publishing or applying it elsewhere.

Probe whether one named selectable value exists inside one GitHub Project field when that field publishes an allowed-value set.

## Use when

- A guard or preparatory step should fail early when one expected project field option is missing but the full field metadata is not otherwise needed later.

## What to provide

- `project_id`: required.
- `field`: required.
- `option`: required.

## Result and boundary

- Usable result fact: `exists`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Inspecting the field's broader metadata such as kind or the full option list; use connector.gh.project.field for the parent field surface.
- Mutating an issue's project field value; use connector.gh.project.issue.field_single_select.set when the workflow should actually set the value after validation.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.project.field`](project-field.md): Parent field probe that returns the field kind and full option list instead of only one boolean option check
- [`connector.gh.project.issue.field_single_select.set`](project-issue-field-single-select-set.md): Action for setting one single-select project field value after the option check succeeds
- [`connector.gh.project.issue.field_iteration.set`](project-issue-field-iteration-set.md): Action for setting one iteration field value when the project field is iteration-backed rather than free-form

## Inspect next

- connector.gh.project.field
- connector.gh.project.issue.field_single_select.set
- connector.gh.project.issue.field_iteration.set

## Exact machine contract

Use `ordo-help operation gh.project.field.option --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_field_option_probe_step

Check whether one named selectable value is valid for the inspected GitHub Project field.

```yaml
      - name: check-done-option
        uses: gh.project.field.option
        with:
          project_id: inputs.project_id
          field: "Status"
          option: "Done"
        register: done_option
```
