# gh.pr.checks

Read normalized status and check-run results from a GitHub pull request head.

Use this when a workflow needs to inspect or change GitHub state. In practice: read normalized status and check-run results from a GitHub pull request head.

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
  "checks": [
    {
      "conclusion": "string",
      "context": "string",
      "kind": "string",
      "name": "string",
      "status": "string",
      "url": "string"
    }
  ],
  "failed_count": "integer",
  "head_sha": "string",
  "overall_state": "string",
  "pending_count": "integer",
  "pull_ref": "string",
  "skipped_count": "integer",
  "success_count": "integer",
  "total_count": "integer"
}
```

## Authoring contract

Probe one GitHub pull request head for normalized status contexts and check runs, including aggregate pass/pending/fail counts for that head SHA. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs CI readiness for one PR there by pull number.
- The workflow needs CI readiness or status context outcomes before recommending merge, rerun, or escalation steps.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Review decisions from humans; use connector.gh.pr.reviews when the workflow cares about approvals or change requests.
- Branch or headline PR metadata unrelated to execution status; use connector.gh.pr for the broader snapshot.

### gh_pr_checks_step

Inspect status contexts and check runs for the pull request head before merge-readiness decisions.

```yaml
  - name: load-pr-checks
    uses: gh.pr.checks
    with:
      repository: inputs.repository
      pull_number: inputs.pull_number
    register: pr_checks
```

## Effects

- None

## Failure modes

- `pull_not_found`
- `checks_unavailable`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.pr.checks`

```json
{
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
          "pull_number": "integer",
          "repository": "string"
        },
        "reference": "gh.pr.checks"
      }
    ],
    "failure_modes": [
      "pull_not_found",
      "checks_unavailable",
      "probe_failed"
    ],
    "inputs": {
      "pull_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "pr.checks",
    "outputs": {
      "checks": [
        {
          "conclusion": "string",
          "context": "string",
          "kind": "string",
          "name": "string",
          "status": "string",
          "url": "string"
        }
      ],
      "failed_count": "integer",
      "head_sha": "string",
      "overall_state": "string",
      "pending_count": "integer",
      "pull_ref": "string",
      "skipped_count": "integer",
      "success_count": "integer",
      "total_count": "integer"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read normalized status and check-run results from a GitHub pull request head.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr.checks",
  "reference": "gh.pr.checks",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
