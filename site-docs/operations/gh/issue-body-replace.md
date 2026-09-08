# gh.issue.body.replace

Replace a GitHub issue body.

Use this when a workflow needs to inspect or change GitHub state. In practice: replace a GitHub issue body.

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
  "changed": "boolean",
  "issue_ref": "string",
  "url": "string"
}
```

## Authoring contract

Replace the entire GitHub issue body with one new body string and report whether the resulting body changed. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow should rewrite one issue body there by issue number.
- The workflow owns the canonical issue description and should rewrite the full body deterministically.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Preserving the current body and merely adding one extra section; use connector.gh.issue.body.append for that narrower update.
- Thread-style follow-up notes; use connector.gh.issue.comment.add when the update belongs in conversation history rather than the body.

### gh_issue_body_replace_step

Rewrite the full issue body when the workflow owns the canonical issue description.

```yaml
  - name: replace-body
    uses: gh.issue.body.replace
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      body: |
        Document the onboarding checklist.

        Checklist synced.
```

## Effects

- replace GitHub issue body

## Failure modes

- `issue_not_found`
- `body_invalid`
- `replace_blocked`

## Requirements

- None

## Example inputs

### `gh.issue.body.replace`

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
      "replace GitHub issue body"
    ],
    "examples": [
      {
        "inputs": {
          "body": "string",
          "issue_number": "integer",
          "repository": "string"
        },
        "reference": "gh.issue.body.replace"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "body_invalid",
      "replace_blocked"
    ],
    "inputs": {
      "body": "string",
      "issue_number": "integer",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.body.replace",
    "outputs": {
      "body": "string",
      "changed": "boolean",
      "issue_ref": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.body.replace'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.body.replace",
  "reference": "gh.issue.body.replace",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
