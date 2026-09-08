# gh.issue.comment.add

Add a comment to a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: add a comment to a GitHub issue.

- Namespace: `gh`
- Kind: `action`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "body": "string",
  "issue_number": "integer",
  "repository": "string"
}
```

## Outputs

```json
{
  "body": "string",
  "comment_id": "string",
  "issue_ref": "string",
  "url": "string"
}
```

## Authoring contract

Add one new comment to an existing GitHub issue and return the created comment id, URL, and body. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow should leave one comment on one issue there.
- The workflow should leave a human-facing note in the issue conversation without rewriting the issue body.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Updating the canonical issue description; use connector.gh.issue.body.append or connector.gh.issue.body.replace when the change belongs in the body itself.
- Reading prior comments; use connector.gh.issue.comments when the workflow needs observation rather than mutation.

### gh_issue_comment_add_step

Add one human-facing follow-up comment to the issue conversation without rewriting the issue body.

```yaml
  - name: add-close-comment
    uses: gh.issue.comment.add
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      body: inputs.close_comment
```

## Effects

- add GitHub issue comment

## Failure modes

- `issue_not_found`
- `body_invalid`
- `comment_blocked`

## Requirements

- None

## Example inputs

### `gh.issue.comment.add`

```json
{
  "body": "string",
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
    "effects": [
      "add GitHub issue comment"
    ],
    "examples": [
      {
        "inputs": {
          "body": "string",
          "issue_number": "integer",
          "repository": "string"
        },
        "reference": "gh.issue.comment.add"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "body_invalid",
      "comment_blocked"
    ],
    "inputs": {
      "body": "string",
      "issue_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.comment.add",
    "outputs": {
      "body": "string",
      "comment_id": "string",
      "issue_ref": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.comment.add'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.comment.add",
  "reference": "gh.issue.comment.add",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
