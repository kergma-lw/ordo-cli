# GitHub Project item details probe model

## Mental model

- This probe returns one project membership slice plus stable GitHub content details for each returned item.
- It stays project-scoped and read-only.
- It does not encode workflow policy, approval logic, or next-step decisions.

## Input shape

- `project_id: string`
- `content_kind: string` optional
- `filters: [{field: string, value: scalar}]` optional
- `content_refs: [string]` optional, where each entry uses `OWNER/REPO#NUMBER`

## Output shape

- `count: integer`
- `items: [object]`
- each item exposes:
  - `item_id`
  - `content_kind`
  - `repository`
  - `number`
  - `title`
  - `url`
  - `state`
  - `label_names`

## Filtering semantics

- `content_kind` is a structural filter.
- `filters` match returned item attributes by equality.
- Item-attribute filters may target either:
  - project-backed fields, using the exact public GitHub Project field name such as `Status` or `Priority`;
  - connector-owned detail attributes, using canonical item output names such as `repository`, `number`, `title`, `url`, or `state`.
- `content_refs` narrows the result to project items whose GitHub content matches one explicit set of repository-number references.
- Each filter compares one field value by equality.
- Multiple constraints compose with AND semantics.

## Detail semantics

- `state` and `label_names` describe the backing GitHub content when that content is an Issue or Pull Request.
- Items without content-backed details, such as DraftIssue-only items, may surface `null` detail fields.
