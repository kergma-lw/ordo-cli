# GitHub pull request creation model

## Public surface

`gh.pr.create` is an effectful action. Its [requirements](../../requirements/connector/gh-pr-create.md) define creation and uncertainty; [listing](gh-pr-list.md) supplies complete observations, [PR inspection](gh-pr.md) supplies by-number detail, and [merge](gh-pr-merge.md) is a separate lifecycle action.

| Input | Obligation and meaning |
| --- | --- |
| `repository` | Optional target `OWNER/REPO`; explicit valid override or bootstrapped context on omission/null. Invalid explicit input does not fall back. |
| `head`, `base`, `title` | Required branch names and title. |
| `body` | Optional text, default empty. |
| `draft` | Required boolean; false is an explicit choice. |
| `head_repository` | Optional full source `OWNER/REPO`, default target repository; required for cross-repository intent. |
| `head_owner` | Optional consistency assertion against the resolved source owner, never a fork-discovery instruction. |

Derive source owner from the exact source repository when omitted. Reject inconsistent owners and same-branch/same-repository requests. Compare repository keys case-insensitively and branch names exactly. Cross-repository API heads carry the source owner qualifier; same-organization cross-repository API `head_repo` carries the source repository NAME.

## Dependency and submission sequence

1. Resolve and validate inputs and target/source identity.
2. Invoke `ctx.call('gh.pr.list', inputs={...})` with resolved `repository`, `head`, `head_owner`, `base`, and `state: open`. This uses the published probe's unchanged signature and full traversal contract.
3. Require complete successful observation and known, consistent candidate identity. Match exact source repository key in addition to target, base, and head.
4. Refuse one exact open match, including draft, as `already_exists`; fail ambiguous matches or an untrustworthy precheck without mutation.
5. With no exact match, issue one POST and validate its response.

## Outcome meaning

| Situation | Outcome meaning | `created` | Number/URL |
| --- | --- | --- | --- |
| Validated HTTP 201 | Successful creation | `true` | Validated new PR identity |
| One existing exact open PR, including draft | Non-OK `already_exists`; no POST | `false` | Observed existing identity |
| Ambiguous matches | Non-OK ambiguity; no POST | `false` | No selected PR |
| Failed/incomplete/unknown precheck | Non-OK `precheck_failed`; no POST | `false` | No selected PR |
| HTTP 422 | Non-OK `create_refused`; retain API errors | `false` | No inferred duplicate identity |
| Malformed 201, timeout, server failure | Non-OK unknown creation result | `null` | No invented successful identity |

The published failure statuses are `input_error`, `precheck_failed`, `ambiguous`, `already_exists`, `api_failed`, `create_refused`, and `creation_unknown`; successful creation is `ok`. Keep runtime status and operation-specific diagnostic meaning distinct.

Published outputs are `repository`, `pull_number`, `pull_ref`, `url`, `created`, `head_repository`, `head_ref`, `head_sha`, `base_repository`, `base_ref`, `base_sha`, `draft`, `state`, `http_status`, `message`, and `errors`. Identity and response facts remain nullable when unavailable; the number in a list item becomes `pull_number` in the action result. The source owner is derived for the dependency/request, not a separate published output. API errors retain structured array/object/string forms when present.

`created: false` on `already_exists` means this invocation did not create a PR, not that no PR exists. `creation_unknown` with `created: null` requires explicit follow-up policy rather than automatic retry.

There is no automatic readback reconciliation, POST retry, atomic uniqueness, or exactly-once guarantee. Concurrent creation may race between the full open observation and submission. Workflow-owned `state: all` history classification is a separate earlier observation; create neither repeats closed-history policy nor becomes find-or-reuse. CI waiting, merge, push, fork, branch cleanup, and extra issue/project operations remain separate surfaces.
