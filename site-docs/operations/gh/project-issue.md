# gh.project.issue

Read one issue's membership and field values in a GitHub Project.

Use this when a workflow needs to inspect or change GitHub state. In practice: read one issue's membership and field values in a GitHub Project.

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
  "issue_number": "integer",
  "project_id": "string",
  "repository": "string"
}
```

## Outputs

```json
{
  "estimate": "number",
  "exists": "boolean",
  "item_id": "string",
  "iteration": "string",
  "priority": "string",
  "size": "string",
  "status": "string",
  "type": "string"
}
```

## Authoring contract

Probe whether one GitHub issue is already attached to one GitHub Project and return the normalized membership item id plus the common project field values that Ordo reads from that membership. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs project membership for one issue there.
- A workflow needs to know whether one issue is already in the target project before deciding to add it or update its project fields.
- Later logic needs one compact project-membership snapshot such as Status, Type, Priority, Iteration, Size, or Estimate for one issue in one project.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Scanning many project items or filtering project membership collections; use connector.gh.project.items or connector.gh.project.items.details for collection-shaped project inspection.
- Adding the issue to the project or mutating project field values; use connector.gh.project.issue.add or the connector.gh.project.issue.field_* setters for those effectful changes.

### gh_project_issue_probe_step

Inspect whether one issue is already attached to the target GitHub Project before deciding whether to add it or mutate its fields.

```yaml
      - name: load-membership
        uses: gh.project.issue
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
        register: membership
```

### gh_project_issue_membership_flow

Probe one issue's project membership, attach it if needed, then set representative single-select, number, and iteration fields through typed project issue surfaces.

```yaml
version: 0
workflow: prepare-project-issue-membership
inputs:
  repository: {}
  issue_number: {}
  project_id: {}
blocks:
  - guards: []
  - steps:
      - name: load-membership
        uses: gh.project.issue
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
        register: membership
      - name: add-to-project
        if: not step.membership.outputs.exists
        uses: gh.project.issue.add
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
        register: membership_add
      - name: set-estimate
        uses: gh.project.issue.field_number.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Estimate"
          value: 3
      - name: set-iteration
        uses: gh.project.issue.field_iteration.set
        with:
          repository: inputs.repository
          issue_number: inputs.issue_number
          project_id: inputs.project_id
          field: "Iteration"
          iteration: "Sprint 12"
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

- None

## Failure modes

- `issue_not_found`
- `project_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.project.issue`

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
    "effects": [],
    "examples": [
      {
        "inputs": {
          "issue_number": "integer",
          "project_id": "string",
          "repository": "string"
        },
        "reference": "gh.project.issue"
      }
    ],
    "failure_modes": [
      "issue_not_found",
      "project_not_found",
      "probe_failed"
    ],
    "inputs": {
      "issue_number": "integer",
      "project_id": "string",
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "project.issue",
    "outputs": {
      "estimate": "number",
      "exists": "boolean",
      "item_id": "string",
      "iteration": "string",
      "priority": "string",
      "size": "string",
      "status": "string",
      "type": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Probe operation 'gh.project.issue'",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "project.issue",
  "reference": "gh.project.issue",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
