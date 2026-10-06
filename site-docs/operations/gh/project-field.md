# GitHub project field

A workflow needs to confirm that a field such as Status or Priority exists before publishing, validating, or mutating project-backed issue data.

Probe one named field in one GitHub Project and return whether it exists, what field kind it is, and which selectable option names it exposes when applicable.

## Use when

- Later logic needs field metadata such as kind or allowed option names instead of only a yes/no answer about one candidate option.

## What to provide

- `project_id`: required.
- `field`: required.

## Result and boundary

- Usable result fact: `exists`.
- Usable result fact: `name`.
- Usable result fact: `kind`.
- Usable result fact: `options`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Checking only whether one named allowed value exists; use connector.gh.project.field.option for that narrower yes/no probe.
- Setting a field value on a project item; use connector.gh.project.issue.field_single_select.set, connector.gh.project.issue.field_number.set, or connector.gh.project.issue.field_iteration.set for the matching field kind rather than this read-only metadata probe.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.project`](project.md): Parent project probe for confirming the project identity before field-specific inspection
- [`connector.gh.project.field.option`](project-field-option.md): Sibling probe for one candidate selectable value rather than the whole field metadata surface
- [`connector.gh.project.issue.field_single_select.set`](project-issue-field-single-select-set.md): Action for writing one selectable field value after field inspection confirms the target field
- [`connector.gh.project.issue.field_number.set`](project-issue-field-number-set.md): Action for writing one numeric field value after field inspection confirms the target field

## Inspect next

- connector.gh.project.field.option
- connector.gh.project.issue.field_single_select.set
- connector.gh.project.issue.field_number.set

## Exact machine contract

Use `ordo-help operation gh.project.field --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_field_probe_step

Inspect one named GitHub Project field and register its kind and option metadata for later decisions.

```yaml
      - name: Load Status field
        uses: gh.project.field
        with:
          project_id: inputs.project_id
          field: "Status"
        register: status_field
```
