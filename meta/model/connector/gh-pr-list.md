# GitHub pull request list probe model

## Public reference and kind

- `gh.pr.list`: `probe`.
- Neighbor `gh.pr` reads one detailed pull request by number. List results supply candidates and identity facts, not a selected PR or a creation/reopening/merge decision.

## Input shape

| Field | Type | Obligation and meaning |
| --- | --- | --- |
| `repository` | string | Optional standard GitHub context/default or explicit `OWNER/REPO` override. |
| `state` | string | Required explicit `open`, `closed`, or `all`. |
| `head` | string | Optional head branch filter. |
| `head_owner` | string | Optional head repository owner (user or organization), requires `head`; not PR author. |
| `base` | string | Optional base branch filter. |

Omitted or null repository uses bootstrapped `connector_contexts.gh.repository`. Invalid explicit repository fails without fallback; unresolved repository fails. Owner plus branch can match multiple repositories belonging to that owner; compare `head_repository_key` to the lowercased expected repository for exact fork identity. No public pagination or limit fields exist.

## Collection and item shape

The successful envelope exposes the resolved `repository`, applied `head`, `head_owner`, `base`, and `state` filters, `items`, `count` (the number of returned items), and `complete: true`. Count is not an independently established remote total. One logical list contains minimal normalized items:

| Field | Meaning |
| --- | --- |
| `number`, `url`, `pull_ref` | Pull request number, URL, and stable pull reference. |
| `state`, `draft` | Observed lifecycle state and draft fact. |
| `merged`, `merged_at` | Nullable merge fact and observed merge timestamp. |
| `head_repository`, `head_owner`, `head_ref`, `head_sha` | Head repository, owner, branch, and commit identity. |
| `head_repository_key` | Nullable lowercase repository identity for case-insensitive matching; raw `head_repository` preserves API case. |
| `base_repository`, `base_ref`, `base_sha` | Base repository, branch, and commit identity. |

The REST list API exposes `merged_at`; it does not provide the detailed-read merged flag. A known timestamp implies true, an explicitly present null `merged_at` implies false, and a missing property or indeterminate evidence implies null. Closed alone does not imply merged. Unknown identity and lifecycle facts must not be invented.

## Retrieval semantics

- REST pull-request listing, not search-index lookup.
- GitHub.com only, explicitly matching the bootstrap authentication host.
- With `head` and `head_owner`, compose the server head filter as `owner:branch`. Without `head_owner`, GitHub does not guarantee bare-head filtering: send only server `state`/`base` filters and match the exact head branch locally over every page. Missing `head_ref` during required local filtering fails rather than discarding the item.
- Internal pagination collects the entire filtered traversal before successful publication; no partial-success collection.
- A subprocess timeout (`subprocess.TimeoutExpired`) returns `pull_list_unavailable` without partial outputs.
- Protective bound: 100 pages with 100 items per page, measured over the traversed collection before local filtering. Remaining pages at the bound cause failure regardless of local match count.
- Validate pagination links, including numeric `/repositories/id/pulls` repository IDs; construct subsequent requests locally instead of following response URLs.
- Contradictory `state: open` with nonnull `merged_at` fails the observation.
- Full traversal is not an atomic concurrency guarantee and does not promise a total remote count.
- Empty success establishes no matches only for the supplied filters; one result establishes one candidate only for those filters.

## Authoring interpretation

For find/create-oriented inspection, recommend explicit `state: all`, optionally narrowed by head/head_owner/base. Workflow logic checks exact repository identity and classifies none, one open, multiple open, and closed history. The canonical fragment gates on a known nonnull `head_repository_key`, then filters with `only(head_repository_key=inputs.head_repository | lower)`. GitHub repository identity is case-insensitive: comparing raw API case to input case could falsely report no PR. Unknown keys remain unavailable and block dependent decisions. Closed/merged history needs workflow rules; unknown facts block dependent decisions. The probe supplies neither creation authorization nor a generic selector.

The separate [gh.pr.create action](gh-pr-create.md) performs a mandatory open-duplicate check; workflow-owned closed-history policy remains separate.

See [requirements](../../requirements/connector/gh-pr-list.md) for failure, discovery, and verified-example obligations.
