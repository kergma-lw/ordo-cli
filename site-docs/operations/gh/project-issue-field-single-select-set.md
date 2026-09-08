# gh.project.issue.field_single_select.set

Set a single-select field for a GitHub Project issue.

Use this when a workflow needs to inspect or change GitHub state. In practice: set a single-select field for a GitHub Project issue.

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
  "option": "string",
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
  "option": "string",
  "project_id": "string"
}
```

## Authoring contract

Set one single-select GitHub Project field on one issue's project item by field name and visible option name. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs to assign one selectable project value for one issue there.
- A workflow needs to assign one selectable project value such as Status or Priority after membership and field-option validation succeed.
- The caller knows the human-facing option label and wants Ordo to resolve the underlying option id automatically.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Writing iteration-backed or numeric project fields; use connector.gh.project.issue.field_iteration.set or connector.gh.project.issue.field_number.set for those different field kinds.
- Checking whether the requested option exists without mutating anything; use connector.gh.project.field.option when the workflow only needs a yes/no option probe.

### gh_project_issue_field_single_select_set_step

Set one selectable project field such as Status by its visible option name after membership is ensured.

```yaml
      - name: set-status
        uses: gh.project.issue.field_single_select.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Status"
          option: "In review"
```

## Effects

- set one GitHub project issue single-select field by field name

## Failure modes

- `issue_not_found`
- `project_not_found`
- `field_not_found`
- `field_kind_unsupported`
- `option_not_found`
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
  },
  {
    "fields": [
      "exists"
    ],
    "probe": "gh.project.field.option",
    "with": {
      "field": "{field}",
      "option": "{option}",
      "project_id": "{project_id}"
    }
  }
]
```

## Invalidated observations

- `gh.project.issue`

## Example inputs

### `gh.project.issue.field_single_select.set`

```json
{
  "field": "string",
  "issue_number": "integer",
  "option": "string",
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
      "set one GitHub project issue single-select field by field name"
    ],
    "examples": [
      {
        "inputs": {
          "field": "string",
          "issue_number": "integer",
          "option": "string",
          "project_id": "string",
          "repository": "string"
        },
        "reference": "gh.project.issue.field_single_select.set"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "project_not_found",
      "field_not_found",
      "field_kind_unsupported",
      "option_not_found",
      "field_update_blocked"
    ],
    "inputs": {
      "field": "string",
      "issue_number": "integer",
      "option": "string",
      "project_id": "string",
      "repository": "string"
    },
    "invalidates_observations": [
      "gh.project.issue"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "project.issue.field_single_select.set",
    "outputs": {
      "changed": "boolean",
      "field": "string",
      "issue_ref": "string",
      "item_id": "string",
      "option": "string",
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
      },
      {
        "fields": [
          "exists"
        ],
        "probe": "gh.project.field.option",
        "with": {
          "field": "{field}",
          "option": "{option}",
          "project_id": "{project_id}"
        }
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'gh.project.issue.field_single_select.set'",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "project.issue.field_single_select.set",
  "reference": "gh.project.issue.field_single_select.set",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
