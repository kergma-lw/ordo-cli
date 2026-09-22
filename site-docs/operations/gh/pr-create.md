# gh.pr.create

Create one PR with explicit draft and exact source repository after a complete gh.pr.list open guard; creation_unknown must not be blindly retried.

Use this when a workflow needs to inspect or change GitHub state. In practice: create one PR with explicit draft and exact source repository after a complete gh.pr.list open guard; creation_unknown must not be blindly retried.

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
  "base": "string",
  "body": "string",
  "draft": "boolean",
  "head": "string",
  "head_owner": "string",
  "head_repository": "string",
  "repository": "string",
  "title": "string"
}
```

## Outputs

```json
{
  "base_ref": "string | null",
  "base_repository": "string | null",
  "base_sha": "string | null",
  "created": "boolean | null",
  "draft": "boolean | null",
  "errors": "array | object | string | null",
  "head_ref": "string | null",
  "head_repository": "string | null",
  "head_sha": "string | null",
  "http_status": "integer | null",
  "message": "string | null",
  "pull_number": "integer | null",
  "pull_ref": "string | null",
  "repository": "string | null",
  "state": "string | null",
  "url": "string | null"
}
```

## Authoring contract

Create one GitHub pull request after a mandatory complete exact-identity open-duplicate precheck.

- GitHub creation: gh.pr.create requires head, base, title, and an explicit boolean draft; body defaults to empty. repository is optional: valid explicit OWNER/REPO overrides connector_contexts.gh.repository; omitted or null uses context, malformed explicit input fails without fallback. head_repository is a full source OWNER/REPO, default target repository; explicit cross-repository intent requires it, with no fork guessing. head_owner is an optional consistency assertion, otherwise derived from the exact source repository. Same-organization head_repo API argument is derived repository NAME. Reject same-branch/same-repository requests. The action uses ctx.call('gh.pr.list', inputs=...) with resolved repository/head/head_owner/base and state: open; require complete traversal and exact case-insensitive head_repository_key identity. One exact open match including draft returns non-OK already_exists with pull_number, url, created=false and no POST; multiple matches return ambiguous; unknown identity and list failure return precheck_failed. No existing match permits one POST. Only validated HTTP 201 means created=true; malformed 201, timeout, or server failure returns creation_unknown with created=null. HTTP 422 is generic create_refused, not universal duplicate evidence; preserve API errors. No POST retry or automatic readback reconciliation. This is not find-or-reuse or closed-history policy: workflow-owned gh.pr.list state: all classification precedes create's separate open check. Concurrent duplicates can race the check: no atomic uniqueness or exactly-once guarantee. No CI waiting, merge, push, fork, branch cleanup, or extra issue/project operations. Inspect connector.gh.pr.create.
- Workflow policy has authorized creation, including any closed-history decision. Register the action result and distinguish runtime status, diagnostic code, pull_number/url identity, and tri-state created; already_exists is non-OK rather than reuse.
- Outputs are repository, pull_number, pull_ref, url, created, head_repository, head_ref, head_sha, base_repository, base_ref, base_sha, draft, state, http_status, message, and errors. Unknown identity/response facts stay null. Failure statuses are input_error, precheck_failed, ambiguous, already_exists, api_failed, create_refused, and creation_unknown; validated creation is ok.
- check, review, plan, explain, and next retain action non-execution; run executes the admitted action. The internal probe does not make creation read-only or authorize POST in analysis modes.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- Find-or-reuse, reopening, or closed-history policy; use a separate gh.pr.list state: all observation and workflow rules.
- Atomic uniqueness, exactly-once effects, automatic retry or readback reconciliation after unknown creation results.
- Waiting for CI, merging, pushing, forking, branch cleanup, or extra issue/project mutations.

### gh_pr_create_new_only

Explicit authorization defaults false and draft defaults true. Check source owner/repository consistency, list all history, require complete known identities, and compare canonical lowercase repository keys. This example refuses every existing exact-source PR, including closed history; that is workflow policy, not an intrinsic action restriction or automatic adoption. Pass the known optional head_repository for the fork. Repository is explicit here but optional through standard gh bootstrap. Save the create result, require confirmed creation and a nonzero integer number, then observe that actual number once. Fixtures prove this exact workflow and strict input handoff, not the action's internal open-only recheck, SDK dependency reuse, POST behavior, or race atomicity. Action failures stop without retry or publication.

```yaml
version: 0
workflow: create-new-branch-pull-request
# Explicit repository is an example choice; the action also supports gh bootstrap.
inputs:
  repository: {}
  head: {}
  head_owner: {}
  head_repository: {}
  head_repository_name:
    description: Source repository name without owner, used to check owner consistency.
  base: {}
  title: {}
  body: {}
  draft:
    default: true
  authorize_create:
    default: false
blocks:
  - steps:
      - name: require-authorization-and-source-identity
        gate:
          all:
            - inputs.authorize_create | eq(true)
            - inputs.draft | is_boolean
            - inputs.head_repository | lower | eq(format("{}/{}", inputs.head_owner, inputs.head_repository_name) | lower)
      - name: list-candidates
        uses: gh.pr.list
        with:
          repository: inputs.repository
          head: inputs.head
          head_owner: inputs.head_owner
          base: inputs.base
          state: 'all'
        register: candidates
      - name: require-complete-known-identity
        gate:
          all:
            - step.candidates.outputs.complete | eq(true)
            - step.candidates.outputs.items | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_repository!=null) | only(head_repository!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_repository_key!=null) | only(head_repository_key!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_owner!=null) | only(head_owner!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_ref!=null) | only(head_ref!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(base_repository!=null) | only(base_repository!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(base_ref!=null) | only(base_ref!="") | length | eq(step.candidates.outputs.count)
      - name: select-exact-source-repository
        value: step.candidates.outputs.items | only(head_repository_key=inputs.head_repository | lower)
        register: exact
      # EXAMPLE workflow policy: refuse all existing PRs, including closed history.
      # The action independently rechecks open PRs; this list is not atomic authorization.
      - name: require-no-existing-pr
        gate: step.exact.outputs.value | length | eq(0)
      - name: create-pr
        uses: gh.pr.create
        with:
          repository: inputs.repository
          head: inputs.head
          head_owner: inputs.head_owner
          head_repository: inputs.head_repository
          base: inputs.base
          title: inputs.title
          body: inputs.body
          draft: inputs.draft
        register: creation
      - name: require-created-identity
        gate:
          all:
            - step.creation.outputs.created | eq(true)
            - step.creation.outputs.pull_number | is_integer
            - step.creation.outputs.pull_number | ne(0)
            - step.creation.outputs.repository | lower | eq(inputs.repository | lower)
      - name: observe-created-number
        uses: gh.pr
        with:
          repository: step.creation.outputs.repository
          pull_number: step.creation.outputs.pull_number
        register: final_pr
      - name: publish-created-pr
        publish:
          pull_number: step.creation.outputs.pull_number
          pull_ref: step.creation.outputs.pull_ref
          url: step.creation.outputs.url
          created: step.creation.outputs.created
          state: step.final_pr.outputs.state

```

## Effects

- create one GitHub pull request after a non-atomic open duplicate precheck

## Failure modes

- `input_error`
- `precheck_failed`
- `ambiguous`
- `already_exists`
- `api_failed`
- `create_refused`
- `creation_unknown`

## Requirements

- None

## Preflight observations

```json
[
  {
    "fields": [
      "items",
      "count",
      "complete"
    ],
    "probe": "gh.pr.list",
    "with": {
      "base": "{base}",
      "head": "{head}",
      "repository": "{repository}",
      "state": "open"
    }
  }
]
```

## Invalidated observations

- `gh.*`

## Example inputs

### `gh.pr.create`

```json
{
  "base": "string",
  "body": "string",
  "draft": "boolean",
  "head": "string",
  "head_owner": "string",
  "head_repository": "string",
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
      "create one GitHub pull request after a non-atomic open duplicate precheck"
    ],
    "examples": [
      {
        "inputs": {
          "base": "string",
          "body": "string",
          "draft": "boolean",
          "head": "string",
          "head_owner": "string",
          "head_repository": "string",
          "repository": "string",
          "title": "string"
        },
        "reference": "gh.pr.create"
      }
    ],
    "failure_modes": [
      "input_error",
      "precheck_failed",
      "ambiguous",
      "already_exists",
      "api_failed",
      "create_refused",
      "creation_unknown"
    ],
    "inputs": {
      "base": "string",
      "body": "string",
      "draft": "boolean",
      "head": "string",
      "head_owner": "string",
      "head_repository": "string",
      "repository": "string",
      "title": "string"
    },
    "invalidates_observations": [
      "gh.*"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "pr.create",
    "outputs": {
      "base_ref": "string | null",
      "base_repository": "string | null",
      "base_sha": "string | null",
      "created": "boolean | null",
      "draft": "boolean | null",
      "errors": "array | object | string | null",
      "head_ref": "string | null",
      "head_repository": "string | null",
      "head_sha": "string | null",
      "http_status": "integer | null",
      "message": "string | null",
      "pull_number": "integer | null",
      "pull_ref": "string | null",
      "repository": "string | null",
      "state": "string | null",
      "url": "string | null"
    },
    "preflight_observations": [
      {
        "fields": [
          "items",
          "count",
          "complete"
        ],
        "probe": "gh.pr.list",
        "with": {
          "base": "{base}",
          "head": "{head}",
          "repository": "{repository}",
          "state": "open"
        }
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Create one PR with explicit draft and exact source repository after a complete gh.pr.list open guard; creation_unknown must not be blindly retried.",
    "tags": [
      "gh",
      "action"
    ]
  },
  "operation_name": "pr.create",
  "reference": "gh.pr.create",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
