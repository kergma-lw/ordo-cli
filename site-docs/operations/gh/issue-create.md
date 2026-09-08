# gh.issue.create

Create a GitHub issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: create a GitHub issue.

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
  "body": "string | null",
  "repository": "string",
  "title": "string"
}
```

## Outputs

```json
{
  "issue_ref": "string",
  "number": "integer",
  "repository": "string",
  "title": "string",
  "url": "string"
}
```

## Authoring contract

Create one new GitHub issue in one repository and return its canonical reference, number, title, and URL for later workflow steps. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow must open a new issue there.
- The workflow must open a new issue and then reuse the returned issue number or URL in later steps.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Editing or commenting on an already existing issue; use the narrower body or comment actions for that follow-up work.
- Reading current issue metadata before deciding whether creation is necessary; use connector.gh.issue or other probe surfaces first when the issue already exists.

### gh_issue_create_step

Create one new GitHub issue and register its returned reference for later steps.

```yaml
  - name: create-issue
    uses: gh.issue.create
    with:
      repository: inputs.repository
      title: inputs.title
      body: inputs.initial_body
    register: created_issue
```

## Effects

- create GitHub issue

## Failure modes

- `repository_not_found`
- `title_invalid`
- `create_blocked`

## Requirements

- None

## Invalidated observations

- `gh.issue`

## Example inputs

### `gh.issue.create`

```json
{
  "body": "string | null",
  "repository": "string",
  "title": "string"
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
      "create GitHub issue"
    ],
    "examples": [
      {
        "inputs": {
          "body": "string | null",
          "repository": "string",
          "title": "string"
        },
        "reference": "gh.issue.create"
      }
    ],
    "failure_modes": [
      "repository_not_found",
      "title_invalid",
      "create_blocked"
    ],
    "inputs": {
      "body": "string | null",
      "repository": "string",
      "title": "string"
    },
    "invalidates_observations": [
      "gh.issue"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "issue.create",
    "outputs": {
      "issue_ref": "string",
      "number": "integer",
      "repository": "string",
      "title": "string",
      "url": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.issue.create'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "issue.create",
  "reference": "gh.issue.create",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
