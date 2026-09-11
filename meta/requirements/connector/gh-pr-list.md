# GitHub pull request list probe requirements

## Role and boundaries

- `gh.pr.list` is a read-only probe for one logical filtered collection of pull requests in a repository, backed by the REST list-pull-requests endpoint, not the search index.
- Use `gh.pr` for a detailed snapshot by `pull_number`; listing does not select the correct PR, authorize creation, reopen a PR, or decide whether to merge. The separate [gh.pr.create action](gh-pr-create.md) performs its own mandatory open-duplicate check after workflow-owned history policy.

## Inputs

- `repository` is optional and follows the shared [repository identity contract](gh-repository-identity.md). A valid explicit ASCII `OWNER/REPO` overrides bootstrapped `connector_contexts.gh.repository`; omitted or null uses context. Malformed explicit input fails without fallback; no resolved repository is an error.
- `state` is required and explicit: `open`, `closed`, or `all`. There is no implicit open-only default.
- `head` optionally filters by head branch; `base` optionally filters by base branch.
- `head_owner` optionally qualifies `head` with a user or organization owning the head repository. It is not the PR author and requires `head`.
- With both fields, send the composed server filter `owner:branch`. GitHub does not document a bare-head guarantee: without `head_owner`, traverse using only server `state`/`base` filters and apply exact `head` branch matching locally across all pages. A missing `head_ref` when local matching is required fails the observation rather than silently discarding the item.
- Owner plus branch is not an exact repository guarantee: one owner may own multiple repositories with the same branch. Exact fork matching requires returned head repository identity.
- There are no public `page`, `cursor`, or `limit` inputs.

## Retrieval and success

- Internal pagination must traverse the full filtered collection before reporting success. Transport, normalization, or incomplete-traversal failures must fail the probe rather than return partial success.
- A subprocess timeout (`subprocess.TimeoutExpired`) normalizes to `pull_list_unavailable`, with no partial outputs.
- Use a protective ceiling of 100 pages of 100 items on the traversed collection before local head filtering. Reaching the ceiling with further pages remaining is failure, even if few local matches exist, not truncating success.
- This probe targets GitHub.com only, matching the authentication bootstrap host. Pagination may advertise repository-name paths or numeric `/repositories/id/pulls` paths; validate numeric repository identity and pagination parameters, then construct requests locally. Never follow response URLs directly.
- Completeness means full traversal of the supplied filters, not an atomic snapshot under concurrent remote changes. No total remote count guarantee is made.
- An empty successful collection means no matches within the provided filters. A single successful item means one candidate within those filters, not automatically the correct PR.

## Minimal item facts

- Each item exposes `number`, `url`, `state`, `draft`, nullable `merged`, `merged_at`, `head_repository`, `head_repository_key`, `head_owner`, `head_ref`, `head_sha`, `base_repository`, `base_ref`, `base_sha`, and `pull_ref`.
- `head_repository` preserves API case; nullable `head_repository_key` is the lowercase repository identity for case-insensitive GitHub repository matching. Unknown identity remains null. Require a known key, then compare it to the lowercased expected repository; a raw case-sensitive comparison must not turn an existing candidate into a false no-match result.
- Preserve repository, branch, and commit identity for exact fork-aware matching. Unavailable facts remain unavailable rather than invented.
- The list API supplies `merged_at`, not the detailed-read merged flag. Derive `merged: true` from a known merge timestamp and `merged: false` from an explicitly present null `merged_at`; a missing property or indeterminate merge evidence yields null. Never convert unknown to false or infer merged solely from `state: closed`.
- An item with `state: open` and nonnull `merged_at` is contradictory and fails the observation.

## Workflow and discovery obligations

- Prefer `state: all` for find/create-oriented inspection so closed history remains visible; optional head/base narrowing is workflow policy.
- Workflows classify none, one open, multiple open, and closed history using observed identity and lifecycle facts. Closed/merged history may require explicit workflow rules; missing facts block decisions that depend on them.
- Even no matches do not automatically authorize creation. Listing carries no generic selection or mutation policy.
- Publish this distinction in `connector.gh`, `connector.gh.pr`, `connector.gh.pr.list`, the feature map, shared overview, and relevant workflow rules. Input-field discovery, operation catalog, and search must expose the probe.
- Canonical verified list fragments must demonstrate filtered `state: all` inspection and workflow-owned classification; creation uses its separate action contract. Text and JSON describe output must satisfy the describe checklist.
- Canonical exact-fork classification gates on a known nonnull `head_repository_key`, then uses `only(head_repository_key=inputs.head_repository | lower)` so differing API/input case still matches the same repository.
