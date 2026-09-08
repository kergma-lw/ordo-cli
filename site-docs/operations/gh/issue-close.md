# gh.issue.close

Close a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: close a GitHub issue.

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
  "repository": "string"
}
```

## Outputs

```json
{
  "closed": "boolean",
  "issue_ref": "string",
  "state": "string"
}
```

## Authoring contract

Close one existing GitHub issue by repository and issue number. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.

- connector_contexts.gh.repository already names the normal repository target and the workflow now needs to close one issue there by issue number.
- A workflow has already decided that the issue should be closed and needs one typed action result instead of a shell-level command.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Explaining the closure in conversation text; add a comment first when the workflow should leave a human-facing note.
- Closing a pull request; use the pull-request connector family for PR-specific lifecycle actions.

### gh_issue_close_step

Close one existing GitHub issue after earlier workflow steps have already selected the target issue number.

```yaml
  - name: close-issue
    uses: gh.issue.close
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
```

## Effects

- close GitHub issue

## Failure modes

- `issue_not_found`
- `close_blocked`

## Requirements

- None

## Example inputs

### `gh.issue.close`

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
    "effects": [
      "close GitHub issue"
    ],
    "examples": [
      {
        "inputs": {
          "issue_number": "integer",
          "repository": "string"
        },
        "reference": "gh.issue.close"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "close_blocked"
    ],
    "inputs": {
      "issue_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.close",
    "outputs": {
      "closed": "boolean",
      "issue_ref": "string",
      "state": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.close'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.close",
  "reference": "gh.issue.close",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
