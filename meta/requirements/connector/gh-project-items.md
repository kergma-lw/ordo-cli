# GitHub Project items probe requirements

## Role

- `gh.project.items` is the public `gh` collection probe for enumerating GitHub Project membership.

## Required question

- The probe must answer which project items match one project scan plus optional structural and field-value constraints.

## Required inputs

- `project_id` is required.
- `content_kind` is optional and narrows the result by structural content kind.
- `filters` is optional and narrows the result by project field values.

## Filter contract

- `filters` is an ordered list of objects shaped as `{field, value}`.
- `field` names one project field by public project-local name.
- `value` is a scalar filter value.
- All filter entries compose with AND semantics.
- V1 filtering is equality-only; it must not introduce OR groups, negation trees, range syntax, or a free-form query language.

## Output contract

- The probe must return:
  - `count`
  - `items`
- Each returned item must expose a normalized addressable shape with:
  - `item_id`
  - `content_kind`
  - `repository`
  - `number`
  - `title`
  - `url`

## Failure contract

- Unknown field names must fail explicitly as `unknown_field`.
- Ambiguous field names must fail explicitly as `ambiguous_field`.
- Unsupported field kinds must fail explicitly as `unsupported_field_type`.
- Invalid filter values must fail explicitly as `invalid_filter_value`.
- Project lookup failure must remain distinct as `project_not_found`.

## Retrieval rule

- The probe should use one connector-owned bulk project retrieval path.
- Ordinary pagination is allowed.
- The implementation must not degrade into per-item or per-field follow-up fetches for the returned item set.

## Discovery rule

- The public contract should be discoverable through `ordo-help operation gh.project.items`.
- Discovery examples should show both:
  - one simple membership scan;
  - one filtered scan.
