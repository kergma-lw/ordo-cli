# gh.repo

Read normalized GitHub repository identity and fork facts.

Use this when a workflow needs to inspect or change GitHub state. In practice: read normalized GitHub repository identity and fork facts.

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
  "repository": "string"
}
```

## Outputs

```json
{
  "archived": "boolean",
  "default_branch": "string | null",
  "id": "string",
  "is_fork": "boolean",
  "parent_repository": "string | null",
  "repository": "string"
}
```

## Authoring contract

Probe one GitHub repository as a normalized identity and fork snapshot, including its default branch, fork status, parent repository, and archived flag. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.

- connector_contexts.gh.repository already names the normal repository target and the workflow needs one repository-level fact probe before deciding whether repo.sync can apply cleanly.
- Later logic needs the repository's canonical name, default branch, or parent fork relationship rather than issue-, PR-, or project-level facts.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Syncing the repository's default branch; use connector.gh.repo.sync for that effectful fork-sync operation.
- Inspecting pull requests, issues, or GitHub Project membership; those remain separate narrower GitHub surfaces.

### gh_repo_probe_step

Inspect one GitHub repository's normalized identity and fork relationship before deciding whether hosted fork sync applies.

```yaml
  - name: inspect-repository
    uses: gh.repo
    register: repo_snapshot
```

### gh_repo_sync_flow

Inspect one hosted fork repository, sync its default branch from the parent repository, then publish the synced branch summary.

```yaml
version: 0
workflow: gh-repo-sync
connector_contexts:
  gh:
    repository: acme/public-mirror # Literal ASCII OWNER/REPO default, not a URL or authorization allowlist.
blocks:
- steps:
  - name: inspect-repository
    uses: gh.repo
    register: repo_snapshot
  - name: sync-default-branch
    uses: gh.repo.sync
    register: sync_result
  - name: publish-summary
    value:
      repository: step.repo_snapshot.outputs.repository
      branch: step.sync_result.outputs.branch
      upstream_repository: step.sync_result.outputs.upstream_repository
```

## Effects

- None

## Failure modes

- `repository_not_found`
- `probe_failed`

## Requirements

- None

## Example inputs

### `gh.repo`

```json
{}
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
        "inputs": {},
        "reference": "gh.repo"
      }
    ],
    "failure_modes": [
      "repository_not_found",
      "probe_failed"
    ],
    "inputs": {
      "repository": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "repo",
    "outputs": {
      "archived": "boolean",
      "default_branch": "string | null",
      "id": "string",
      "is_fork": "boolean",
      "parent_repository": "string | null",
      "repository": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Read normalized GitHub repository identity and fork facts.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "repo",
  "reference": "gh.repo",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
