# gh.pr.comments

Read regular conversation comments from a GitHub pull request.

Use this when a workflow needs to inspect or change GitHub state. In practice: read regular conversation comments from a GitHub pull request.

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
  "comments": [
    "object"
  ],
  "pull_ref": "string",
  "total_count": "integer"
}
```

## Authoring contract

Probe the regular conversation thread on one GitHub pull request as top-level discussion comments plus total count metadata. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs top-level PR discussion there by pull number.
- The workflow needs human conversation on the PR itself before summarizing discussion or deciding whether follow-up is needed.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Line-level review discussion attached to changed files; use connector.gh.pr.review_comments for code-anchored comments.
- Submitted review decisions such as APPROVED or CHANGES_REQUESTED; use connector.gh.pr.reviews for review verdicts.

### gh_pr_comments_step

Inspect the top-level pull request conversation thread with one explicit limit and register the resulting comment list.

```yaml
  - name: load-pr-comments
    uses: gh.pr.comments
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_comments
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

### `gh.pr.comments`

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
        "reference": "gh.pr.comments"
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
    "name": "pr.comments",
    "outputs": {
      "comments": [
        "object"
      ],
      "pull_ref": "string",
      "total_count": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read regular conversation comments from a GitHub pull request.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr.comments",
  "reference": "gh.pr.comments",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
