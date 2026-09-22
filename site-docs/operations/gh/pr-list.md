# gh.pr.list

List GitHub.com REST pull requests by explicit state (open|closed|all) and optional branches; bare head is filtered locally across all pages. Complete traversal is not an atomic snapshot.

Use this when a workflow needs to inspect or change GitHub state. In practice: list GitHub.com REST pull requests by explicit state (open|closed|all) and optional branches; bare head is filtered locally across all pages. Complete traversal is not an atomic snapshot.

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
  "base": "string",
  "head": "string",
  "head_owner": "string",
  "repository": "string",
  "state": "string"
}
```

## Outputs

```json
{
  "base": "string",
  "complete": "boolean",
  "count": "integer",
  "head": "string",
  "head_owner": "string",
  "items": [
    {
      "base_ref": "string",
      "base_repository": "string",
      "base_sha": "string",
      "draft": "boolean",
      "head_owner": "string",
      "head_ref": "string",
      "head_repository": "string",
      "head_repository_key": "string",
      "head_sha": "string",
      "merged": "boolean",
      "merged_at": "string",
      "number": "integer",
      "pull_ref": "string",
      "state": "string",
      "url": "string"
    }
  ],
  "repository": "string",
  "state": "string"
}
```

## Authoring contract

Probe one full filtered GitHub pull-request collection through REST list PRs, with minimal lifecycle and head/base identity facts for workflow-owned candidate classification.

- GitHub candidate discovery: gh.pr.list observes a full filtered REST pull-request collection, not the search index. repository is optional with the standard connector_contexts.gh.repository default and explicit OWNER/REPO override. state is required: open|closed|all. Prefer state: all for find/create-oriented inspection, optionally narrowed by head/head_owner/base. head_owner is the head repository owner (user or organization), not PR author, and requires head; owner plus branch is not exact repository identity. Compare returned head_repository for exact fork matching. Internal pagination has no public page/cursor/limit; incomplete traversal fails. head with head_owner composes server owner:branch; bare head is matched exactly locally across all state/base pages because GitHub does not guarantee bare-head filtering. Missing head_ref for local filtering fails. The 100-page ceiling applies before local filtering. GitHub.com only, matching bootstrap authentication. Full traversal is not an atomic snapshot or a total remote count guarantee. Empty success means no matches within the supplied filters; one result is a candidate, not automatically the correct PR. Workflow rules classify none, one open, multiple open, and closed history; unknown facts block dependent decisions. Closed/merged history may require additional workflow rules. Listing does not authorize creation, reopening, or merge. gh.pr reads detailed facts by pull_number; gh.pr.create is a separate action with its own mandatory open check. Inspect connector.gh.pr.list for canonical filtered classification fragments.
- The repository argument is optional: a valid explicit ASCII OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error.
- Supply required state explicitly as open, closed, or all. head is an optional branch filter, head_owner an optional user/org qualifier requiring head, and base an optional base branch filter. Narrowing head/base is workflow policy, not an operation requirement.
- Items expose number, url, state, draft, merged, merged_at, head_repository, head_repository_key, head_owner, head_ref, head_sha, base_repository, base_ref, base_sha, and pull_ref. Preserve these identities for exact fork matching before detailed gh.pr inspection.
- GitHub repository identity is case-insensitive. Raw head_repository preserves API case; nullable head_repository_key is the lowercase identity. Gate on a known nonnull key, then match with only(head_repository_key=inputs.head_repository | lower). Raw case-sensitive comparison could falsely report no PR when API/input case differs; unknown keys block dependent decisions.
- The list API supplies merged_at: a known merge timestamp derives merged=true, explicitly present null merged_at derives false, and missing or indeterminate evidence derives null. Never turn unknown into false or infer merged merely from closed state.
- An item with state: open and nonnull merged_at is contradictory and fails the observation.
- With head and head_owner, compose the server head filter as owner:branch. Without head_owner, send only state/base server filters and apply exact head matching locally across all pages; GitHub docs do not guarantee bare-head filtering. Missing head_ref when local filtering is required fails rather than silently discarding the item.
- Success requires full filtered traversal; transport, normalization, or pagination failure cannot publish partial success. A protective cap of 100 pages of 100 items applies to the traversed collection before local filtering and fails if more pages remain, even with few matches; it is not a public result limit.
- A subprocess timeout (subprocess.TimeoutExpired) returns pull_list_unavailable with no partial outputs.
- GitHub.com only, matching the bootstrap authentication host. Pagination accepts validated repository-name and numeric /repositories/id/pulls paths, validates repository IDs and pagination parameters, and constructs requests locally; never follow response URLs directly.
- repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass.

### Boundaries

- A generic correct-PR selector, creation authorization, reopening, or merge decisions. gh.pr.create performs a separate mandatory open-duplicate check after workflow-owned history policy.
- Detailed facts for a known pull_number; use gh.pr. List facts are minimal and unavailable facts must remain unknown.
- PR author filtering: head_owner means head repository owner. One owner can own multiple repositories with the same branch; owner plus branch is not an exact repository guarantee.
- Public page, cursor, or limit controls, partial-success truncation, search-index completeness, atomic concurrency completeness, or a total remote count guarantee.

### gh_pr_list_no_pr

List all matching candidates with head, head_owner, base and state: all; repository is optional through standard gh bootstrap but supplied explicitly here. Reject unknown source identity and head_repository_key before exact repository filtering: compare the probe's lowercase key with inputs.head_repository | lower, retaining raw head_repository and case-sensitive branch names. Owner plus branch is not exact fork identity. Conditional workflow steps publish no PR, one open, ambiguous open, or closed history; nullable merged facts remain unknown. This observer selects no PR number and performs no automatic action. A workflow selecting a number must first gate on exactly one matching open PR. A complete full API traversal is not an atomic snapshot, and an empty list never authorizes creation after concurrent changes. Fixture execution proves this exact YAML's decisions, not live API traversal or bootstrap.

```yaml
version: 0
workflow: classify-branch-pull-requests
# repository is explicit here; gh.pr.list also supports standard gh bootstrap.
inputs:
  repository:
    description: Target OWNER/REPO repository.
  head:
    description: Source branch name, without an owner prefix.
  head_owner:
    description: Source owner login (not a repository identity).
  head_repository:
    description: Exact source OWNER/REPO; one owner may have multiple forks.
  base:
    description: Target branch name.
blocks:
  - steps:
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
            - step.candidates.outputs.items | only(head_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_repository="") | length | eq(0)
            - step.candidates.outputs.items | only(head_repository_key!=null) | only(head_repository_key!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_owner=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_owner="") | length | eq(0)
            - step.candidates.outputs.items | only(head_ref=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_ref="") | length | eq(0)
            - step.candidates.outputs.items | only(base_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(base_ref=null) | length | eq(0)
      - name: select-exact-source-repository
        value: step.candidates.outputs.items | only(head_repository_key=inputs.head_repository | lower)
        register: exact
      - name: publish-observation
        publish:
          count: step.exact.outputs.value | length
          open: step.exact.outputs.value | only(state="open") | length
          closed: step.exact.outputs.value | only(state="closed") | length
          merged: step.exact.outputs.value | only(merged=true) | length
          merged_unknown: step.exact.outputs.value | only(merged=null) | length
      - name: classify-no-pr
        if: step.exact.outputs.value | length | eq(0)
        publish:
          classification: 'no_pr'
      - name: classify-one-open
        if: step.exact.outputs.value | only(state="open") | length | eq(1)
        publish:
          classification: 'exactly_one_open'
      - name: classify-ambiguous-open
        if:
          all:
            - step.exact.outputs.value | only(state="open") | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | ne(1)
        publish:
          classification: 'ambiguous_multiple_open'
      - name: classify-closed-history
        if:
          all:
            - step.exact.outputs.value | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | eq(0)
        publish:
          classification: 'only_closed_history'

```

### gh_pr_list_exactly_one_open

List all matching candidates with head, head_owner, base and state: all; repository is optional through standard gh bootstrap but supplied explicitly here. Reject unknown source identity and head_repository_key before exact repository filtering: compare the probe's lowercase key with inputs.head_repository | lower, retaining raw head_repository and case-sensitive branch names. Owner plus branch is not exact fork identity. Conditional workflow steps publish no PR, one open, ambiguous open, or closed history; nullable merged facts remain unknown. This observer selects no PR number and performs no automatic action. A workflow selecting a number must first gate on exactly one matching open PR. A complete full API traversal is not an atomic snapshot, and an empty list never authorizes creation after concurrent changes. Fixture execution proves this exact YAML's decisions, not live API traversal or bootstrap.

```yaml
version: 0
workflow: classify-branch-pull-requests
# repository is explicit here; gh.pr.list also supports standard gh bootstrap.
inputs:
  repository:
    description: Target OWNER/REPO repository.
  head:
    description: Source branch name, without an owner prefix.
  head_owner:
    description: Source owner login (not a repository identity).
  head_repository:
    description: Exact source OWNER/REPO; one owner may have multiple forks.
  base:
    description: Target branch name.
blocks:
  - steps:
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
            - step.candidates.outputs.items | only(head_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_repository="") | length | eq(0)
            - step.candidates.outputs.items | only(head_repository_key!=null) | only(head_repository_key!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_owner=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_owner="") | length | eq(0)
            - step.candidates.outputs.items | only(head_ref=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_ref="") | length | eq(0)
            - step.candidates.outputs.items | only(base_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(base_ref=null) | length | eq(0)
      - name: select-exact-source-repository
        value: step.candidates.outputs.items | only(head_repository_key=inputs.head_repository | lower)
        register: exact
      - name: publish-observation
        publish:
          count: step.exact.outputs.value | length
          open: step.exact.outputs.value | only(state="open") | length
          closed: step.exact.outputs.value | only(state="closed") | length
          merged: step.exact.outputs.value | only(merged=true) | length
          merged_unknown: step.exact.outputs.value | only(merged=null) | length
      - name: classify-no-pr
        if: step.exact.outputs.value | length | eq(0)
        publish:
          classification: 'no_pr'
      - name: classify-one-open
        if: step.exact.outputs.value | only(state="open") | length | eq(1)
        publish:
          classification: 'exactly_one_open'
      - name: classify-ambiguous-open
        if:
          all:
            - step.exact.outputs.value | only(state="open") | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | ne(1)
        publish:
          classification: 'ambiguous_multiple_open'
      - name: classify-closed-history
        if:
          all:
            - step.exact.outputs.value | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | eq(0)
        publish:
          classification: 'only_closed_history'

```

### gh_pr_list_ambiguous_multiple_open

List all matching candidates with head, head_owner, base and state: all; repository is optional through standard gh bootstrap but supplied explicitly here. Reject unknown source identity and head_repository_key before exact repository filtering: compare the probe's lowercase key with inputs.head_repository | lower, retaining raw head_repository and case-sensitive branch names. Owner plus branch is not exact fork identity. Conditional workflow steps publish no PR, one open, ambiguous open, or closed history; nullable merged facts remain unknown. This observer selects no PR number and performs no automatic action. A workflow selecting a number must first gate on exactly one matching open PR. A complete full API traversal is not an atomic snapshot, and an empty list never authorizes creation after concurrent changes. Fixture execution proves this exact YAML's decisions, not live API traversal or bootstrap.

```yaml
version: 0
workflow: classify-branch-pull-requests
# repository is explicit here; gh.pr.list also supports standard gh bootstrap.
inputs:
  repository:
    description: Target OWNER/REPO repository.
  head:
    description: Source branch name, without an owner prefix.
  head_owner:
    description: Source owner login (not a repository identity).
  head_repository:
    description: Exact source OWNER/REPO; one owner may have multiple forks.
  base:
    description: Target branch name.
blocks:
  - steps:
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
            - step.candidates.outputs.items | only(head_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_repository="") | length | eq(0)
            - step.candidates.outputs.items | only(head_repository_key!=null) | only(head_repository_key!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_owner=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_owner="") | length | eq(0)
            - step.candidates.outputs.items | only(head_ref=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_ref="") | length | eq(0)
            - step.candidates.outputs.items | only(base_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(base_ref=null) | length | eq(0)
      - name: select-exact-source-repository
        value: step.candidates.outputs.items | only(head_repository_key=inputs.head_repository | lower)
        register: exact
      - name: publish-observation
        publish:
          count: step.exact.outputs.value | length
          open: step.exact.outputs.value | only(state="open") | length
          closed: step.exact.outputs.value | only(state="closed") | length
          merged: step.exact.outputs.value | only(merged=true) | length
          merged_unknown: step.exact.outputs.value | only(merged=null) | length
      - name: classify-no-pr
        if: step.exact.outputs.value | length | eq(0)
        publish:
          classification: 'no_pr'
      - name: classify-one-open
        if: step.exact.outputs.value | only(state="open") | length | eq(1)
        publish:
          classification: 'exactly_one_open'
      - name: classify-ambiguous-open
        if:
          all:
            - step.exact.outputs.value | only(state="open") | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | ne(1)
        publish:
          classification: 'ambiguous_multiple_open'
      - name: classify-closed-history
        if:
          all:
            - step.exact.outputs.value | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | eq(0)
        publish:
          classification: 'only_closed_history'

```

### gh_pr_list_only_closed_history

List all matching candidates with head, head_owner, base and state: all; repository is optional through standard gh bootstrap but supplied explicitly here. Reject unknown source identity and head_repository_key before exact repository filtering: compare the probe's lowercase key with inputs.head_repository | lower, retaining raw head_repository and case-sensitive branch names. Owner plus branch is not exact fork identity. Conditional workflow steps publish no PR, one open, ambiguous open, or closed history; nullable merged facts remain unknown. This observer selects no PR number and performs no automatic action. A workflow selecting a number must first gate on exactly one matching open PR. A complete full API traversal is not an atomic snapshot, and an empty list never authorizes creation after concurrent changes. Fixture execution proves this exact YAML's decisions, not live API traversal or bootstrap.

```yaml
version: 0
workflow: classify-branch-pull-requests
# repository is explicit here; gh.pr.list also supports standard gh bootstrap.
inputs:
  repository:
    description: Target OWNER/REPO repository.
  head:
    description: Source branch name, without an owner prefix.
  head_owner:
    description: Source owner login (not a repository identity).
  head_repository:
    description: Exact source OWNER/REPO; one owner may have multiple forks.
  base:
    description: Target branch name.
blocks:
  - steps:
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
            - step.candidates.outputs.items | only(head_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_repository="") | length | eq(0)
            - step.candidates.outputs.items | only(head_repository_key!=null) | only(head_repository_key!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_owner=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_owner="") | length | eq(0)
            - step.candidates.outputs.items | only(head_ref=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_ref="") | length | eq(0)
            - step.candidates.outputs.items | only(base_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(base_ref=null) | length | eq(0)
      - name: select-exact-source-repository
        value: step.candidates.outputs.items | only(head_repository_key=inputs.head_repository | lower)
        register: exact
      - name: publish-observation
        publish:
          count: step.exact.outputs.value | length
          open: step.exact.outputs.value | only(state="open") | length
          closed: step.exact.outputs.value | only(state="closed") | length
          merged: step.exact.outputs.value | only(merged=true) | length
          merged_unknown: step.exact.outputs.value | only(merged=null) | length
      - name: classify-no-pr
        if: step.exact.outputs.value | length | eq(0)
        publish:
          classification: 'no_pr'
      - name: classify-one-open
        if: step.exact.outputs.value | only(state="open") | length | eq(1)
        publish:
          classification: 'exactly_one_open'
      - name: classify-ambiguous-open
        if:
          all:
            - step.exact.outputs.value | only(state="open") | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | ne(1)
        publish:
          classification: 'ambiguous_multiple_open'
      - name: classify-closed-history
        if:
          all:
            - step.exact.outputs.value | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | eq(0)
        publish:
          classification: 'only_closed_history'

```

### gh_pr_list_unknown_metadata

List all matching candidates with head, head_owner, base and state: all; repository is optional through standard gh bootstrap but supplied explicitly here. Reject unknown source identity and head_repository_key before exact repository filtering: compare the probe's lowercase key with inputs.head_repository | lower, retaining raw head_repository and case-sensitive branch names. Owner plus branch is not exact fork identity. Conditional workflow steps publish no PR, one open, ambiguous open, or closed history; nullable merged facts remain unknown. This observer selects no PR number and performs no automatic action. A workflow selecting a number must first gate on exactly one matching open PR. A complete full API traversal is not an atomic snapshot, and an empty list never authorizes creation after concurrent changes. Fixture execution proves this exact YAML's decisions, not live API traversal or bootstrap.

```yaml
version: 0
workflow: classify-branch-pull-requests
# repository is explicit here; gh.pr.list also supports standard gh bootstrap.
inputs:
  repository:
    description: Target OWNER/REPO repository.
  head:
    description: Source branch name, without an owner prefix.
  head_owner:
    description: Source owner login (not a repository identity).
  head_repository:
    description: Exact source OWNER/REPO; one owner may have multiple forks.
  base:
    description: Target branch name.
blocks:
  - steps:
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
            - step.candidates.outputs.items | only(head_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_repository="") | length | eq(0)
            - step.candidates.outputs.items | only(head_repository_key!=null) | only(head_repository_key!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_owner=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_owner="") | length | eq(0)
            - step.candidates.outputs.items | only(head_ref=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_ref="") | length | eq(0)
            - step.candidates.outputs.items | only(base_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(base_ref=null) | length | eq(0)
      - name: select-exact-source-repository
        value: step.candidates.outputs.items | only(head_repository_key=inputs.head_repository | lower)
        register: exact
      - name: publish-observation
        publish:
          count: step.exact.outputs.value | length
          open: step.exact.outputs.value | only(state="open") | length
          closed: step.exact.outputs.value | only(state="closed") | length
          merged: step.exact.outputs.value | only(merged=true) | length
          merged_unknown: step.exact.outputs.value | only(merged=null) | length
      - name: classify-no-pr
        if: step.exact.outputs.value | length | eq(0)
        publish:
          classification: 'no_pr'
      - name: classify-one-open
        if: step.exact.outputs.value | only(state="open") | length | eq(1)
        publish:
          classification: 'exactly_one_open'
      - name: classify-ambiguous-open
        if:
          all:
            - step.exact.outputs.value | only(state="open") | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | ne(1)
        publish:
          classification: 'ambiguous_multiple_open'
      - name: classify-closed-history
        if:
          all:
            - step.exact.outputs.value | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | eq(0)
        publish:
          classification: 'only_closed_history'

```

## Effects

- None

## Failure modes

- `input_error`
- `pull_list_unavailable`

## Requirements

- None

## Example inputs

### `gh.pr.list`

```json
{
  "base": "string",
  "head": "string",
  "head_owner": "string",
  "repository": "string",
  "state": "string"
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
          "base": "string",
          "head": "string",
          "head_owner": "string",
          "repository": "string",
          "state": "string"
        },
        "reference": "gh.pr.list"
      }
    ],
    "failure_modes": [
      "input_error",
      "pull_list_unavailable"
    ],
    "inputs": {
      "base": "string",
      "head": "string",
      "head_owner": "string",
      "repository": "string",
      "state": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "pr.list",
    "outputs": {
      "base": "string",
      "complete": "boolean",
      "count": "integer",
      "head": "string",
      "head_owner": "string",
      "items": [
        {
          "base_ref": "string",
          "base_repository": "string",
          "base_sha": "string",
          "draft": "boolean",
          "head_owner": "string",
          "head_ref": "string",
          "head_repository": "string",
          "head_repository_key": "string",
          "head_sha": "string",
          "merged": "boolean",
          "merged_at": "string",
          "number": "integer",
          "pull_ref": "string",
          "state": "string",
          "url": "string"
        }
      ],
      "repository": "string",
      "state": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "List GitHub.com REST pull requests by explicit state (open|closed|all) and optional branches; bare head is filtered locally across all pages. Complete traversal is not an atomic snapshot.",
    "tags": [
      "gh",
      "probe"
    ]
  },
  "operation_name": "pr.list",
  "reference": "gh.pr.list",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
