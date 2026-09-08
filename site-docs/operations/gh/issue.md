# gh.issue

Read a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: read a GitHub issue.

- Namespace: `gh`
- Kind: `probe`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "issue_number": "integer",
  "repository": "string"
}
```

## Outputs

```json
{
  "assignees": [
    "object"
  ],
  "author": "object",
  "body": "string",
  "closed": "boolean",
  "closed_at": "string",
  "comments": "object",
  "created_at": "string",
  "id": "string",
  "labels": [
    "object"
  ],
  "milestone": "object",
  "number": "number",
  "project_items": [
    "object"
  ],
  "reaction_groups": [
    "object"
  ],
  "repository": "object",
  "state": "string",
  "state_reason": "string",
  "title": "string",
  "updated_at": "string",
  "url": "string"
}
```

## Authoring contract

Probe one GitHub issue as a typed snapshot of its current metadata, body, labels, assignees, and project-item context. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.

- connector_contexts.gh.repository already names the normal repository target and workflow logic now needs one issue snapshot from that repository by issue number.
- Workflow logic needs to inspect one issue before deciding whether to comment, edit the body, close it, or publish a summary.
- A guard or later step needs typed issue facts such as state, title, labels, or body rather than a coarse shell response.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Listing the issue's comment thread only; use connector.gh.issue.comments for that narrower conversation surface.
- Mutating the issue; use connector.gh.issue.create, connector.gh.issue.comment.add, connector.gh.issue.body.append, connector.gh.issue.body.replace, or connector.gh.issue.close for effectful changes.

### gh_issue_probe_step

Inspect one GitHub issue and register the typed snapshot for later workflow decisions.

```yaml
  - name: inspect-created-issue
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
  - name: create-issue
    uses: gh.issue.create
    with:
      repository: inputs.repository
      title: inputs.title
      body: inputs.initial_body
    register: created_issue
  - name: inspect-created-issue
    uses: gh.issue
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
    register: issue_snapshot
  - name: add-close-comment
    uses: gh.issue.comment.add
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      body: inputs.close_comment
  - name: append-body-note
    uses: gh.issue.body.append
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      text: "Follow-up note: checklist synced."
      separator: "\n\n"
  - name: replace-body
    uses: gh.issue.body.replace
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      body: |
        Document the onboarding checklist.

        Checklist synced.
  - name: list-comments
    uses: gh.issue.comments
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      limit: 20
    register: comments_snapshot
  - name: close-issue
    uses: gh.issue.close
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
```

## Effects

- None

## Failure modes

- `issue_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.issue`

```json
{
  "issue_number": "integer",
  "repository": "string"
}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [
      "host",
      "viewer",
      "scopes",
      "repository"
    ],
    "prerequisites": [
      "gh binary available",
      "GitHub auth available"
    ]
  },
  "document_kind": "operation",
  "namespace": "gh",
  "operation": {
    "deprecated": false,
    "effects": [],
    "examples": [
      {
        "inputs": {
          "issue_number": "integer",
          "repository": "string"
        },
        "reference": "gh.issue"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "probe_failed"
    ],
    "inputs": {
      "issue_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "issue",
    "outputs": {
      "assignees": [
        "object"
      ],
      "author": "object",
      "body": "string",
      "closed": "boolean",
      "closed_at": "string",
      "comments": "object",
      "created_at": "string",
      "id": "string",
      "labels": [
        "object"
      ],
      "milestone": "object",
      "number": "number",
      "project_items": [
        "object"
      ],
      "reaction_groups": [
        "object"
      ],
      "repository": "object",
      "state": "string",
      "state_reason": "string",
      "title": "string",
      "updated_at": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'gh.issue'",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "issue",
  "reference": "gh.issue",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
