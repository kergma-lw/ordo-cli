# GitHub pull request creation requirements

## Role and inputs

- `gh.pr.create` is an action creating one pull request after a mandatory open-duplicate observation. It is not find-or-reuse and does not authorize creation from closed history.
- Optional `repository` follows the shared repository identity contract: valid explicit ASCII `OWNER/REPO` overrides bootstrapped `connector_contexts.gh.repository`; omitted or null uses context. Malformed explicit values fail without fallback; unresolved repository fails.
- `head`, `base`, and `title` are required. `body` is optional and defaults to empty text. `draft` is a required boolean, including explicit `false`.
- Optional `head_repository` is the full source `OWNER/REPO`, defaulting to the target repository. Optional `head_owner` asserts consistency with the resolved source owner; absent owner is derived from that exact repository.
- Explicit cross-repository creation requires `head_repository`; an owner alone cannot request fork guessing. Same-organization cross-repository requests derive the API's `head_repo` argument from the source repository NAME, not its full identity.
- Reject the same head and base branch in the same repository. Repository identity comparison is case-insensitive; branch identity is exact.

## Mandatory observation before mutation

- Call the published `gh.pr.list` probe through `ctx.call`, supplying already-resolved target repository, head, source owner, base, and explicit `state: open`.
- Require successful full traversal (`complete: true`), then match exact head repository identity using its case-insensitive key alongside target/base/head identity. Owner plus branch alone is insufficient.
- One exact open match, including a draft, returns non-OK `already_exists`, the existing number and URL, and `created: false`; no POST occurs. This is refusal, not successful reuse.
- Multiple exact matches are ambiguous and fail. Unknown or contradictory identity, incomplete traversal, and list failures fail the precheck. No failure or ambiguity may be interpreted as an empty successful list.
- The precheck does not inspect closed history or implement reopening policy. A user workflow may first use [gh.pr.list](gh-pr-list.md) with `state: all`, classify closed history under workflow policy, and then invoke create with its separate mandatory open check.

## Single submission and uncertainty

- With no exact open match and a trustworthy complete observation, submit exactly one POST.
- Only a validated HTTP 201 response establishes `created: true`. A malformed 201, timeout, or server failure after submission leaves `created: null`: the creation result is unknown, not known false.
- HTTP 422 is generic `create_refused`, not universal duplicate evidence. Preserve upstream structured errors and useful diagnostics.
- Do not retry POST or perform readback reconciliation automatically. A future retry/reconciliation contract requires separate agreement.
- Full traversal and the subsequent POST are not atomic. A concurrent creator can race the check; this action promises neither atomic uniqueness nor exactly-once effects.
- The action does not wait for CI, merge, push, fork, clean up branches, or perform additional issue/project mutations.

## Publication and verification

- Publish the input, output, refusal, ambiguity, and unknown-result contract in operation discovery, `connector.gh.pr.create`, GitHub neighbors, features, overview, model, capabilities, operations, search, and authoring guidance.
- Verify explicit and context repository examples, exact fork identity, draft duplicates, incomplete/unknown observations, validated and malformed 201, 422 errors, and uncertain submissions. Canonical describe examples must be verified source, with definition, applicability, exclusions, and nearest neighbors visible in text and JSON.
- `check`, `review`, `plan`, `explain`, and `next` retain action non-execution and must expose the action contract without invoking its POST or fabricating create outputs. `run` invokes the admitted action once; its internal probe remains read-only. The [SDK dependency contract](../../model/connector/plugin-sdk-api.md) does not add action composition or allow probe-to-action hidden mutation.
