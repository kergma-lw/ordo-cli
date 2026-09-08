# gh.pr.timeline

Read normalized lifecycle events from a GitHub pull request timeline.

Use this when a workflow needs to inspect or change GitHub state. In practice: read normalized lifecycle events from a GitHub pull request timeline.

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
  "events": [
    "object"
  ],
  "pull_ref": "string",
  "total_count": "integer"
}
```

## Authoring contract

Probe one GitHub pull request timeline as normalized lifecycle events such as ready-for-review, review requests, and base-ref changes. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs lifecycle history there for one PR number.
- The workflow needs temporal PR lifecycle facts that are not equivalent to comments, checks, or the current PR snapshot alone.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- The current PR state only; use connector.gh.pr when timeline history is unnecessary.
- Top-level discussion or submitted review verdicts; use comments or reviews for those narrower surfaces.

### gh_pr_timeline_step

Inspect lifecycle events from the pull request timeline with one explicit limit before summarizing history.

```yaml
  - name: load-pr-timeline
    uses: gh.pr.timeline
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_timeline
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

### `gh.pr.timeline`

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
        "reference": "gh.pr.timeline"
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
    "name": "pr.timeline",
    "outputs": {
      "events": [
        "object"
      ],
      "pull_ref": "string",
      "total_count": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read normalized lifecycle events from a GitHub pull request timeline.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr.timeline",
  "reference": "gh.pr.timeline",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
