# GitHub project items details

A workflow needs project-scoped item matching plus richer content details that are not present on connector.gh.project.items alone.

Probe one GitHub Project as a normalized item collection with stable content details such as issue state and label names in addition to the base membership facts.

## Use when

- Later branching or publishing depends on issue or pull-request state, or on label_names for the matched project-backed content.

## What to provide

- `project_id`: required.
- `content_kind`: optional.
- `filters`: optional.
- `content_refs`: optional.

## Result and boundary

- Usable result fact: `count`.
- Usable result fact: `items`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Cheap project membership scans where repository, number, title, and url are already enough; use connector.gh.project.items for the lighter collection probe.
- Checking or mutating one specific issue membership; use connector.gh.project.issue or connector.gh.project.issue.* for the one-item membership family.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.project.items`](project-items.md): Parent collection probe for lighter normalized project items without extra content details
- [`connector.gh.project.issue`](project-issue.md): Sibling probe for one issue-specific membership snapshot instead of a collection result set
- [`connector.gh.issue`](issue.md): Sibling probe for one repository issue snapshot outside the project-collection context
- [`connector.gh.project.field`](project-field.md): Sibling probe for project field metadata rather than matched item details

## Inspect next

- connector.gh.project.items
- connector.gh.project.issue
- connector.gh.issue

## Exact machine contract

Use `ordo-help operation gh.project.items.details --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_items_details_probe_step

Load richer project-backed content details such as state and label_names for a previously narrowed project item subset.

```yaml
      - name: load-ready-item-details
        uses: gh.project.items.details
        with:
          project_id: inputs.project_id
          content_kind: "Issue"
          filters:
            - field: "Status"
              value: "Ready"
          content_refs:
            - "owner/repo#7"
            - "owner/repo#8"
        register: ready_item_details
```
