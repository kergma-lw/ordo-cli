# GitHub pr list

Find pull requests matching a repository, branch, and lifecycle state before the workflow makes its own decision.

Use gh.pr.list to list matching pull requests with the identity and lifecycle facts needed for workflow decisions.

## Use when

- Supply state as open, closed, or all; optionally narrow the list with head, head_owner, or base.
- Use the GitHub context repository or supply an explicit OWNER/REPO. head_owner identifies the source repository owner, not the pull request author.
- Each result item provides number, pull_ref, and url; state and draft; merged and merged_at; and head_repository, head_repository_key, head_owner, head_ref, head_sha, base_repository, base_ref, and base_sha. Use complete and count before relying on items. Compare head_repository_key with the intended source repository for exact fork matching, head_ref and head_sha for the source revision, and base_repository, base_ref, and base_sha for the destination. One match is a candidate, not automatic authorization.
- A closed pull request is not necessarily merged. Use the returned merged state when it is known; do not infer a merge from closed state, and treat an unknown merged state as unavailable evidence.
- The result is a current observation, not an atomic snapshot. Unknown or incomplete facts must block a dependent decision.

## What to provide

- Provide required `state` as `open`, `closed`, or `all`. Provide `repository` only to override the workflow GitHub repository context.
- Optionally provide `head`, `head_owner`, and `base` to narrow the collection. `head_owner` requires `head` and identifies a source repository owner, not the pull request author.
- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `head`: optional.
- `head_owner`: conditional.
- `base`: optional.
- `state`: required.

## Result and boundary

- A complete result has `complete=true`, `count`, and `items`. Each item exposes `pull_ref`, `number`, `url`, state and merge facts, source identity and `head_sha`, and destination identity and `base_sha` for later workflow decisions.
- The probe fails rather than returning a partial collection. A complete collection is still not an atomic snapshot or automatic PR selection; concurrent changes and unknown item facts require another observation or a workflow decision.
- Usable result fact: `repository`.
- Usable result fact: `head_owner`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Selecting the correct pull request automatically, authorizing creation, reopening, or merging.
- Detailed facts for a known pull request number; use gh.pr instead.
- Pull request author filtering; a repository owner can have several repositories with the same branch name.

## Related references

Use these related operations when the workflow needs a neighboring decision or observation.


- [`connector.gh.pr`](pr.md): Inspect one known pull request by number.
- [`connector.gh.pr.create`](pr-create.md): Create a new pull request after a workflow decision.
- [`workflow-rules`](../../topics/workflow-rules.md): Keep identity, ambiguity, and history decisions in workflow logic.

## Exact machine contract

Use `ordo-help operation gh.pr.list --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_list_exactly_one_open

List all matching candidates with head, head_owner, base, and state: all. Require complete results and known source identity before comparing the intended repository. The workflow publishes no pull request, exactly one open pull request, ambiguity, or closed history; it does not select a number or take an action automatically. A later workflow decision must require exactly one matching open pull request.

```yaml
version: 0
workflow: classify-branch-pull-requests
# The explicit repository keeps the target visible in this example.
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
