# GitHub Project items probe model

## Public reference

- `gh.project.items`

## Kind

- `probe`

## Mental model

- This probe enumerates one GitHub Project item collection and then applies narrow contract-owned filtering.
- It is not a policy-named derived probe such as `active_stories` or `ready_tasks`.

## Input shape

- `project_id: string`
- `content_kind: string` optional
- `filters: [{field: string, value: scalar}]` optional

## Output shape

```json
{
  "count": 2,
  "items": [
    {
      "item_id": "PVTI_xxx",
      "content_kind": "Issue",
      "repository": "owner/repo",
      "number": 7,
      "title": "Implement project items probe",
      "url": "https://github.com/owner/repo/issues/7"
    }
  ]
}
```

## Filtering semantics

- `content_kind` is a structural filter.
- `filters` match project fields by field name.
- Each filter compares one field value by equality.
- Multiple filters compose with AND semantics.
- Missing field values on one item mean that item does not match.

## Discovery examples

### Let-bound scan

```yaml
let:
  ready_items: >-
    gh.project.items(project_id=inputs.project_id, filters=inputs.filters)

blocks:
  - guards:
      - ready_items.count != 0
```

### Direct filtered call

```yaml
uses: gh.project.items
with:
  project_id: ${inputs.project_id}
  content_kind: Issue
  filters:
    - field: Status
      value: Ready
```
