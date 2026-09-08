# gh.pr

Read pull request metadata from GitHub.

Use this when a workflow needs to inspect or change GitHub state. In practice: read pull request metadata from GitHub.

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
  "pull_number": "integer",
  "repository": "string"
}
```

## Outputs

```json
{
  "additions": "integer",
  "author": "object",
  "base_ref": "string",
  "body": "string",
  "changed_files": "integer",
  "commits_count": "integer",
  "created_at": "string",
  "deletions": "integer",
  "draft": "boolean",
  "head_ref": "string",
  "head_sha": "string",
  "mergeable": "boolean",
  "mergeable_state": "string",
  "number": "integer",
  "repository": "string",
  "review_decision": "string",
  "state": "string",
  "title": "string",
  "updated_at": "string",
  "url": "string"
}
```

## Authoring contract

Probe one GitHub pull request as a typed metadata snapshot for title, body, refs, review state, mergeability, and change totals without loading comments, reviews, checks, or diff content. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.

- connector_contexts.gh.repository already names the normal repository target and workflow logic now needs one PR snapshot there by pull number.
- Workflow logic needs the pull request's current headline facts before deciding which narrower PR surfaces to inspect next.
- A later step needs branch refs, draft/state flags, review decision, or change totals from one normalized PR snapshot.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Conversation history, submitted reviews, line comments, checks, or lifecycle events; use the dedicated PR sibling surfaces for those narrower views.
- Mutating or merging the pull request; this published surface is observation only.

### gh_pr_probe_step

Inspect one pull request headline snapshot before branching into narrower diff, review, comment, and checks surfaces.

```yaml
  - name: load-pr
    uses: gh.pr
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
    register: pr
```

### gh_pr_full_inspection_flow

Inspect one pull request through metadata, diff, comments, reviews, review comments, checks, and timeline surfaces, then publish a digest.

```yaml
version: 0
workflow: inspect-pr
inputs:
  repository: kergma-lw/ordo-cli # Literal ASCII OWNER/REPO, not a URL; explicit other repositories remain allowed.
  pull_number: 42
blocks:
- steps:
  - name: load-pr
    uses: gh.pr
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
    register: pr
  - name: load-pr-diff
    uses: gh.pr.diff
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_diff
  - name: load-pr-comments
    uses: gh.pr.comments
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_comments
  - name: load-pr-reviews
    uses: gh.pr.reviews
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_reviews
  - name: load-pr-review-comments
    uses: gh.pr.review_comments
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_review_comments
  - name: load-pr-checks
    uses: gh.pr.checks
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
    register: pr_checks
  - name: load-pr-timeline
    uses: gh.pr.timeline
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
      limit: 20
    register: pr_timeline
  - name: publish-pr-inspection
    publish:
      summary: "Pull request inspection loaded"
      pull_ref:
        format: "{}#{}"
        args:
        - inputs.repository
        - inputs.pull_number
      title: step.pr.outputs.title
      head_sha: step.pr.outputs.head_sha
      changed_file_count: step.pr_diff.outputs.total_files
      comment_count: step.pr_comments.outputs.total_count
      review_count: step.pr_reviews.outputs.total_count
      review_comment_count: step.pr_review_comments.outputs.total_count
      check_count: step.pr_checks.outputs.total_count
      timeline_count: step.pr_timeline.outputs.total_count
```

## Effects

- None

## Failure modes

- `pull_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.pr`

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
        "reference": "gh.pr"
      }
    ],
    "failure_modes": [
      "pull_not_found",
      "probe_failed"
    ],
    "inputs": {
      "pull_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "pr",
    "outputs": {
      "additions": "integer",
      "author": "object",
      "base_ref": "string",
      "body": "string",
      "changed_files": "integer",
      "commits_count": "integer",
      "created_at": "string",
      "deletions": "integer",
      "draft": "boolean",
      "head_ref": "string",
      "head_sha": "string",
      "mergeable": "boolean",
      "mergeable_state": "string",
      "number": "integer",
      "repository": "string",
      "review_decision": "string",
      "state": "string",
      "title": "string",
      "updated_at": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read normalized metadata from a GitHub pull request.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr",
  "reference": "gh.pr",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
