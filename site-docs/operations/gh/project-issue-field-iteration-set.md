# gh.project.issue.field_iteration.set

Set an iteration field for a GitHub Project issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: set an iteration field for a GitHub Project issue.

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
  "field": "string",
  "issue_number": "integer",
  "iteration": "string",
  "project_id": "string",
  "repository": "string"
}
```

## Outputs

```json
{
  "changed": "boolean",
  "field": "string",
  "issue_ref": "string",
  "item_id": "string",
  "iteration": "string",
  "project_id": "string"
}
```

## Authoring contract

Set one iteration-valued GitHub Project field on one issue's project item by field name and human iteration title. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs to move one project-backed issue there into a named iteration.
- A workflow needs to move one project-backed issue into a named iteration such as Sprint 12 after membership already exists or can be resolved.
- The caller knows the field by its project-visible name and wants Ordo to resolve the underlying iteration id and item id automatically.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Attaching the issue to the project in the first place; use connector.gh.project.issue.add when membership may still be missing.
- Updating numeric or single-select fields; use connector.gh.project.issue.field_number.set or connector.gh.project.issue.field_single_select.set for those different field kinds.

### gh_project_issue_field_iteration_set_step

Move the project-backed issue into one named iteration after membership is already ensured.

```yaml
      - name: set-iteration
        uses: gh.project.issue.field_iteration.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Iteration"
          iteration: "Sprint 12"
```

## Effects

- set one GitHub project issue iteration field by field name

## Failure modes

- `issue_not_found`
- `project_not_found`
- `field_not_found`
- `field_kind_unsupported`
- `iteration_not_found`
- `field_update_blocked`

## Requirements

- None

## Preflight observations

```json
[
  {
    "fields": [
      "exists"
    ],
    "probe": "gh.project.issue",
    "with": {
      "issue_number": "{issue_number}",
      "project_id": "{project_id}",
      "repository": "{repository}"
    }
  },
  {
    "fields": [
      "exists"
    ],
    "probe": "gh.project.field",
    "with": {
      "field": "{field}",
      "project_id": "{project_id}"
    }
  }
]
```

## Invalidated observations

- `gh.project.issue`

## Example inputs

### `gh.project.issue.field_iteration.set`

```json
{
  "field": "string",
  "issue_number": "integer",
  "iteration": "string",
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
      "set one GitHub project issue iteration field by field name"
    ],
    "examples": [
      {
        "inputs": {
          "field": "string",
          "issue_number": "integer",
          "iteration": "string",
          "project_id": "string",
          "repository": "string"
        },
        "reference": "gh.project.issue.field_iteration.set"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "project_not_found",
      "field_not_found",
      "field_kind_unsupported",
      "iteration_not_found",
      "field_update_blocked"
    ],
    "inputs": {
      "field": "string",
      "issue_number": "integer",
      "iteration": "string",
      "project_id": "string",
      "repository": "string"
    },
    "invalidates_observations": [
      "gh.project.issue"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "project.issue.field_iteration.set",
    "outputs": {
      "changed": "boolean",
      "field": "string",
      "issue_ref": "string",
      "item_id": "string",
      "iteration": "string",
      "project_id": "string"
    },
    "preflight_observations": [
      {
        "fields": [
          "exists"
        ],
        "probe": "gh.project.issue",
        "with": {
          "issue_number": "{issue_number}",
          "project_id": "{project_id}",
          "repository": "{repository}"
        }
      },
      {
        "fields": [
          "exists"
        ],
        "probe": "gh.project.field",
        "with": {
          "field": "{field}",
          "project_id": "{project_id}"
        }
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.project.issue.field_iteration.set'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "project.issue.field_iteration.set",
  "reference": "gh.project.issue.field_iteration.set",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
