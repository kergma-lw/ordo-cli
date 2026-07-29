# GitHub Project items probe model

## Public reference

- `gh.project.items`

## Kind

- `probe`

## Mental model

- This probe resolves contract-owned filters and projects them into one GitHub Project item query whenever the backend can express them directly.
- The connector validates project field names and filter literals before issuing the item scan.
- It is not a policy-named derived probe such as `active_stories` or `ready_tasks`.

## Input shape

- `project_id: string`
- `content_kind: string` optional
- `filters: [{field: string, value: scalar}]` optional
- `content_refs: [string]` optional, where each entry uses `OWNER/REPO#NUMBER`

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
- `content_refs` narrows the result to project items whose GitHub content matches one explicit set of repository-number references.
- Each filter compares one field value by equality.
- Multiple filters compose with AND semantics.
- The connector should push supported constraints into the GitHub Project item query instead of hydrating all field values for all items.
- When `content_refs` is present, the connector should switch to one bulk content-addressed retrieval path rather than a project-wide item scan.

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
