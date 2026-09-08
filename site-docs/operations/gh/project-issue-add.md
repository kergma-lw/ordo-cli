# gh.project.issue.add

Add a GitHub issue to a GitHub Project.

Use this when a workflow needs to inspect or change GitHub state. In practice: add a GitHub issue to a GitHub Project.

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
  "project_id": "string",
  "repository": "string"
}
```

## Outputs

```json
{
  "added": "boolean",
  "issue_ref": "string",
  "item_id": "string",
  "project_id": "string"
}
```

## Authoring contract

Add one GitHub issue to one GitHub Project and return the project item id, while staying idempotent when the issue is already attached. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs to ensure one issue there becomes a project item.
- A workflow has one concrete issue and one target project and needs to ensure that the issue becomes a project item before later project-field updates.
- The workflow wants one typed membership-creation result instead of shelling out to ad hoc gh project mutations.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Checking membership without changing anything; use connector.gh.project.issue when the real question is whether the issue is already in the project.
- Updating Status, Estimate, Iteration, or another project-backed field after membership exists; use the narrower connector.gh.project.issue.field_* setters for those follow-up mutations.

### gh_project_issue_add_step

Attach the issue to the target GitHub Project only when the earlier membership probe reported exists=false.

```yaml
      - name: add-to-project
        if: not step.membership.outputs.exists
        uses: gh.project.issue.add
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
        register: membership_add
```

## Effects

- add GitHub issue to project

## Failure modes

- `issue_not_found`
- `project_not_found`
- `add_blocked`

## Requirements

- None

## Invalidated observations

- `gh.project.issue`

## Example inputs

### `gh.project.issue.add`

```json
{
  "issue_number": "integer",
  "project_id": "string",
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
      "add GitHub issue to project"
    ],
    "examples": [
      {
        "inputs": {
          "issue_number": "integer",
          "project_id": "string",
          "repository": "string"
        },
        "reference": "gh.project.issue.add"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "project_not_found",
      "add_blocked"
    ],
    "inputs": {
      "issue_number": "integer",
      "project_id": "string",
      "repository": "string"
    },
    "invalidates_observations": [
      "gh.project.issue"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "project.issue.add",
    "outputs": {
      "added": "boolean",
      "issue_ref": "string",
      "item_id": "string",
      "project_id": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.project.issue.add'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "project.issue.add",
  "reference": "gh.project.issue.add",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
