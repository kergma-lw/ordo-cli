# gh.pr.diff

Read normalized change content from a GitHub pull request.

Use this when a workflow needs to inspect or change GitHub state. In practice: read normalized change content from a GitHub pull request.

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
  "files": [
    "object"
  ],
  "pull_ref": "string",
  "total_files": "integer"
}
```

## Authoring contract

Probe one GitHub pull request diff as normalized changed-file summaries with patch excerpts, rename metadata, and binary/truncation signals. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs changed-file detail there for one PR number.
- The workflow needs to reason about which files changed or inspect bounded patch content without parsing raw git output itself.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Overall PR headline facts such as title, branch refs, or review decision; use connector.gh.pr for that metadata snapshot.
- Conversation or review decision surfaces; use comments, review_comments, or reviews when the workflow is about discussion rather than code changes.

### gh_pr_diff_step

Inspect changed files and bounded diff content from one pull request before reacting to code-level changes.

```yaml
  - name: load-pr-diff
    uses: gh.pr.diff
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_diff
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

### `gh.pr.diff`

```json
{
  "pull_number": 42
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
          "pull_number": 42
        },
        "reference": "gh.pr.diff"
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
    "name": "pr.diff",
    "outputs": {
      "files": [
        "object"
      ],
      "pull_ref": "string",
      "total_files": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read normalized change content from a GitHub pull request.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr.diff",
  "reference": "gh.pr.diff",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
