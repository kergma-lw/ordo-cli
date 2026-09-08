# gh.project.issue.field_number.set

Set a number field for a GitHub Project issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: set a number field for a GitHub Project issue.

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
  "project_id": "string",
  "repository": "string",
  "value": "number"
}
```

## Outputs

```json
{
  "changed": "boolean",
  "field": "string",
  "issue_ref": "string",
  "item_id": "string",
  "project_id": "string",
  "value": "number"
}
```

## Authoring contract

Set one number-valued GitHub Project field on one issue's project item by field name and numeric value. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs to write one numeric project field for one issue there.
- A workflow needs to write one numeric project field such as Estimate to a project-backed issue item after membership and field resolution succeed.
- The caller wants Ordo to reject non-numeric values early instead of discovering that mismatch only inside a raw project mutation.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Writing selectable or iteration-backed project fields; use connector.gh.project.issue.field_single_select.set or connector.gh.project.issue.field_iteration.set for those different field kinds.
- Reading the current field value without changing it; use connector.gh.project.issue when the workflow only needs the observed membership snapshot.

### gh_project_issue_field_number_set_step

Write one numeric project field such as Estimate after the issue is attached to the project.

```yaml
      - name: set-estimate
        uses: gh.project.issue.field_number.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Estimate"
          value: 3
```

## Effects

- set one GitHub project issue number field by field name

## Failure modes

- `issue_not_found`
- `project_not_found`
- `field_not_found`
- `field_kind_unsupported`
- `field_value_invalid`
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

### `gh.project.issue.field_number.set`

```json
{
  "field": "string",
  "issue_number": "integer",
  "project_id": "string",
  "repository": "string",
  "value": "number"
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
      "set one GitHub project issue number field by field name"
    ],
    "examples": [
      {
        "inputs": {
          "field": "string",
          "issue_number": "integer",
          "project_id": "string",
          "repository": "string",
          "value": "number"
        },
        "reference": "gh.project.issue.field_number.set"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "project_not_found",
      "field_not_found",
      "field_kind_unsupported",
      "field_value_invalid",
      "field_update_blocked"
    ],
    "inputs": {
      "field": "string",
      "issue_number": "integer",
      "project_id": "string",
      "repository": "string",
      "value": "number"
    },
    "invalidates_observations": [
      "gh.project.issue"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "project.issue.field_number.set",
    "outputs": {
      "changed": "boolean",
      "field": "string",
      "issue_ref": "string",
      "item_id": "string",
      "project_id": "string",
      "value": "number"
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
    "summary": "Action operation 'gh.project.issue.field_number.set'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "project.issue.field_number.set",
  "reference": "gh.project.issue.field_number.set",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
