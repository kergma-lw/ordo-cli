# gh.pr.reviews

Read submitted reviews from a GitHub pull request.

Use this when a workflow needs to inspect or change GitHub state. In practice: read submitted reviews from a GitHub pull request.

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
  "limit": "integer",
  "pull_number": "integer",
  "repository": "string"
}
```

## Outputs

```json
{
  "pull_ref": "string",
  "reviews": [
    "object"
  ],
  "total_count": "integer"
}
```

## Authoring contract

Probe submitted GitHub pull-request reviews as typed review records with verdict, author, timestamp, and optional reviewed commit id. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs submitted review records there by pull number.
- The workflow needs reviewer decisions such as APPROVED or CHANGES_REQUESTED without reconstructing them from comments or timeline events.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Free-form top-level discussion; use connector.gh.pr.comments when the workflow needs ordinary PR conversation.
- Per-line feedback details; use connector.gh.pr.review_comments for code-anchored remarks.

### gh_pr_reviews_step

Inspect submitted pull-request reviews with one explicit limit before interpreting approval or change-request history.

```yaml
  - name: load-pr-reviews
    uses: gh.pr.reviews
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_reviews
```

## Effects

- None

## Failure modes

- `pull_not_found`
- `limit_invalid`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.pr.reviews`

```json
{
  "limit": "integer",
  "pull_number": "integer",
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
          "limit": "integer",
          "pull_number": "integer",
          "repository": "string"
        },
        "reference": "gh.pr.reviews"
      }
    ],
    "failure_modes": [
      "pull_not_found",
      "limit_invalid",
      "probe_failed"
    ],
    "inputs": {
      "limit": "integer",
      "pull_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "pr.reviews",
    "outputs": {
      "pull_ref": "string",
      "reviews": [
        "object"
      ],
      "total_count": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read submitted reviews from a GitHub pull request.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr.reviews",
  "reference": "gh.pr.reviews",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
