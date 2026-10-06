# GitHub issue

the workflow's GitHub repository context already names the normal repository target and workflow logic now needs one issue snapshot from that repository by issue number.

Probe one GitHub issue as a typed snapshot of its current metadata, body, labels, assignees, and project-item context. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.

## Use when

- Workflow logic needs to inspect one issue before deciding whether to comment, edit the body, close it, or publish a summary.
- A guard or later step needs typed issue facts such as state, title, labels, or body rather than a coarse shell response.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.

## Result and boundary

- Usable result fact: `id`.
- Usable result fact: `number`.
- Usable result fact: `title`.
- Usable result fact: `state`.
- Usable result fact: `closed`.
- Usable result fact: `url`.
- Usable result fact: `body`.
- Usable result fact: `author`.
- Usable result fact: `labels`.
- Usable result fact: `assignees`.
- Usable result fact: `milestone`.
- Usable result fact: `created_at`.
- Usable result fact: `updated_at`.
- Usable result fact: `closed_at`.
- Usable result fact: `comments`.
- Usable result fact: `reaction_groups`.
- Usable result fact: `repository`.
- Usable result fact: `state_reason`.
- Usable result fact: `project_items`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Listing the issue's comment thread only; use connector.gh.issue.comments for that narrower conversation surface.
- Mutating the issue; use connector.gh.issue.create, connector.gh.issue.comment.add, connector.gh.issue.body.append, connector.gh.issue.body.replace, or connector.gh.issue.close for effectful changes.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.gh`: Parent GitHub connector family for issue, pull request, and project operations
- [`connector.gh.issue.comments`](issue-comments.md): Sibling probe for the issue comment thread rather than the issue snapshot itself
- [`connector.gh.issue.comment.add`](issue-comment-add.md): Action for adding one new issue comment after inspection
- [`connector.gh.issue.close`](issue-close.md): Action for closing the issue after inspection or cleanup

## Inspect next

- connector.gh.issue.comments
- connector.gh.issue.comment.add
- connector.gh.issue.body.replace
- connector.gh.issue.close

## Exact machine contract

Use `ordo-help operation gh.issue --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_issue_probe_step

Inspect one GitHub issue and register the typed snapshot for later workflow decisions.

```yaml
  - name: Inspect created issue
    uses: gh.issue
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
    register: issue_snapshot
```
### gh_issue_full_maintenance_flow

Create an issue, inspect it, comment on it, edit the body, inspect comments, and close it with typed GitHub issue operations.

```yaml
version: 0
workflow: gh-issue-maintenance
inputs:
  repository: acme/mobile-app
  title: Refresh onboarding guide
  initial_body: Document the onboarding checklist.
  close_comment: Closing after syncing the checklist.
blocks:
- steps:
  # Create and inspect the issue.
  - name: Create issue
    uses: gh.issue.create
    with:
      repository: inputs.repository
      title: inputs.title
      body: inputs.initial_body
    register: created_issue
  - name: Inspect created issue
    uses: gh.issue
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
    register: issue_snapshot

  # Update the issue discussion and body.
  - name: Add closing comment
    uses: gh.issue.comment.add
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      body: inputs.close_comment
  - name: Append body note
    uses: gh.issue.body.append
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      text: "Follow-up note: checklist synced."
      separator: "\n\n"
  - name: Replace issue body
    uses: gh.issue.body.replace
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      body: |
        Document the onboarding checklist.

        Checklist synced.
  # Review the final issue state and close it.
  - name: List issue comments
    uses: gh.issue.comments
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      limit: 20
    register: comments_snapshot
  - name: Close issue
    uses: gh.issue.close
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
```
