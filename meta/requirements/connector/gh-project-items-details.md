# GitHub Project item details probe requirements

## Role

- `gh.project.items.details` is the public `gh` detail probe for project-scoped GitHub content details.

## Required question

- The probe must answer which project items match one project-scoped selection and what stable GitHub content details those matched items expose.

## Required inputs

- `project_id` is required.
- `content_kind` is optional and narrows the result by structural content kind.
- `filters` is optional and narrows the result by project field values.
- `content_refs` is optional and narrows the result by explicit GitHub content references using `OWNER/REPO#NUMBER` format.

## Output contract

- The probe must return:
  - `count`
  - `items`
- Each returned item must expose:
  - `item_id`
  - `content_kind`
  - `repository`
  - `number`
  - `title`
  - `url`
  - `state`
  - `label_names`

## Failure contract

- Unknown field names must fail explicitly as `unknown_field`.
- Ambiguous field names must fail explicitly as `ambiguous_field`.
- Unsupported field kinds must fail explicitly as `unsupported_field_type`.
- Invalid filter values must fail explicitly as `invalid_filter_value`.
- Invalid content references must fail explicitly as `invalid_content_ref`.
- Project lookup failure must remain distinct as `project_not_found`.

## Retrieval rule

- The probe should reuse one connector-owned bulk project retrieval path for project-wide scans.
- The probe should translate supported structural and field-equality constraints into the backend project item query before paginating results.
- When `content_refs` is present, the probe should use one bulk content-addressed GraphQL retrieval path without per-ref follow-up requests.
- The probe should fetch only the stable detail fields that belong to its public contract.
- The implementation must not degrade into per-item or per-field follow-up fetches for the returned item set.

## Probe addition rationale

- The probe exposes stable GitHub content facts that are not available through `gh.project.items` outputs.
- The probe should remain narrow and must not expand into a catch-all issue body or comment retrieval surface.
