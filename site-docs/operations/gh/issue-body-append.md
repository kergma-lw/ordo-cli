# gh.issue.body.append

Append text to a GitHub issue body.

Use this when a workflow needs to inspect or change GitHub state. In practice: append text to a GitHub issue body.

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
  "issue_number": "integer",
  "repository": "string",
  "separator": "string | null",
  "text": "string"
}
```

## Outputs

```json
{
  "body": "string",
  "changed": "boolean",
  "issue_ref": "string",
  "url": "string"
}
```

## Authoring contract

Append one text fragment to the end of an existing GitHub issue body, optionally separated from the prior body by one explicit separator. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow should append one note to one issue body there.
- The workflow should preserve the current issue body and add one extra section, note, or footer to it.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Regenerating the whole canonical body from scratch; use connector.gh.issue.body.replace for a full rewrite.
- Adding conversational discussion that belongs in the comment thread instead of the issue body; use connector.gh.issue.comment.add.

### gh_issue_body_append_step

Append one extra note to the existing issue body while preserving earlier body content.

```yaml
  - name: append-body-note
    uses: gh.issue.body.append
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      text: "Follow-up note: checklist synced."
      separator: "\n\n"
```

## Effects

- append text to GitHub issue body

## Failure modes

- `issue_not_found`
- `text_invalid`
- `append_blocked`

## Requirements

- None

## Example inputs

### `gh.issue.body.append`

```json
{
  "issue_number": "integer",
  "repository": "string",
  "separator": "string | null",
  "text": "string"
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
      "append text to GitHub issue body"
    ],
    "examples": [
      {
        "inputs": {
          "issue_number": "integer",
          "repository": "string",
          "separator": "string | null",
          "text": "string"
        },
        "reference": "gh.issue.body.append"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "text_invalid",
      "append_blocked"
    ],
    "inputs": {
      "issue_number": "integer",
      "repository": "string",
      "separator": "string | null",
      "text": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.body.append",
    "outputs": {
      "body": "string",
      "changed": "boolean",
      "issue_ref": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.body.append'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.body.append",
  "reference": "gh.issue.body.append",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
