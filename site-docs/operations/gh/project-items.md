# GitHub project items

A workflow needs one project-scoped membership scan across many items rather than one issue-specific membership lookup.

Probe one GitHub Project as a collection of normalized project items, with optional narrowing by content kind, project field filters, and explicit GitHub content references.

## Use when

- Later logic only needs stable collection facts such as repository, number, title, url, and content kind without loading richer content details like issue state and labels.

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

- Inspecting one specific issue's membership or project field values; use connector.gh.project.issue for the one-issue membership surface.
- Loading richer content details such as issue state and label_names for the matched items; use connector.gh.project.items.details for that heavier collection probe.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.project`](project.md): Parent project probe for confirming the target project identity before collection scans
- [`connector.gh.project.items.details`](project-items-details.md): Sibling probe for the same collection scan with richer issue and pull-request details
- [`connector.gh.project.issue`](project-issue.md): Sibling probe for one issue-specific membership snapshot instead of a collection scan
- [`connector.gh.project.field`](project-field.md): Sibling probe for one project field definition when the workflow needs field metadata rather than matched items

## Inspect next

- connector.gh.project.items.details
- connector.gh.project.issue
- connector.gh.project.field

## Exact machine contract

Use `ordo-help operation gh.project.items --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_project_items_probe_step

Scan one GitHub Project for matching items before branching on collection size or reusing the matched item list later.

```yaml
      - name: load-ready-items
        uses: gh.project.items
        with:
          project_id: inputs.project_id
          content_kind: "Issue"
          filters:
            - field: "Status"
              value: "Ready"
        register: ready_items
```
### gh_project_items_collection_flow

Load one light project-item collection first, then load richer item details for an explicit matched subset before publishing a compact summary.

```yaml
version: 0
workflow: inspect-project-item-collections
inputs:
  project_id: {}
blocks:
  - guards: []
  - steps:
      - name: load-ready-items
        uses: gh.project.items
        with:
          project_id: inputs.project_id
          content_kind: "Issue"
          filters:
            - field: "Status"
              value: "Ready"
        register: ready_items
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
      - name: publish-summary
        publish:
          ready_count: step.ready_items.outputs.count
          detailed_count: step.ready_item_details.outputs.count
          summary: "Project item collections loaded"
```
