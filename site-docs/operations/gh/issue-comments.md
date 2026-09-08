# gh.issue.comments

Read comments from a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: read comments from a GitHub issue.

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
  "limit": "integer",
  "repository": "string"
}
```

## Outputs

```json
{
  "comments": [
    "object"
  ],
  "issue_ref": "string",
  "total_count": "number"
}
```

## Authoring contract

Probe the comment thread of one GitHub issue as a typed list of recent comments plus total count metadata. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and workflow logic now needs prior discussion for one issue there.
- Workflow logic needs to inspect prior discussion, count comments, or publish a compact conversation summary before taking another step.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Reading the issue's main body, labels, or state; use connector.gh.issue for the broader issue snapshot.
- Posting a new comment; use connector.gh.issue.comment.add for that effectful change.

### gh_issue_comments_step

Inspect the issue comment thread with one explicit limit and register the resulting comment snapshot.

```yaml
  - name: list-comments
    uses: gh.issue.comments
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      limit: 20
    register: comments_snapshot
```

## Effects

- None

## Failure modes

- `issue_not_found`
- `limit_invalid`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.issue.comments`

```json
{
  "issue_number": "integer",
  "limit": "integer",
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
          "limit": "integer",
          "repository": "string"
        },
        "reference": "gh.issue.comments"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "limit_invalid",
      "probe_failed"
    ],
    "inputs": {
      "issue_number": "integer",
      "limit": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "issue.comments",
    "outputs": {
      "comments": [
        "object"
      ],
      "issue_ref": "string",
      "total_count": "number"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'gh.issue.comments'",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "issue.comments",
  "reference": "gh.issue.comments",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
