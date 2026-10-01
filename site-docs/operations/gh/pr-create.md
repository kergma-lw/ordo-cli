# GitHub pr create

Create one new GitHub pull request from a known source branch when the workflow has explicitly authorized it.

Create one pull request only when no matching open pull request is already known.

## Use when

- Supply the source branch, target branch, title, and an explicit draft value. The body is optional and defaults to empty.
- Use the workflow's GitHub repository context or name the target repository explicitly. When the source is a fork or another repository, supply head_repository with that exact source repository; the action does not guess forks. head_owner, when supplied, must name that source repository's owner; this prevents a branch owner from being confused with a different fork.
- Authorize creation and decide any closed-history policy in the workflow before this action. A matching open pull request is refused rather than reused.
- When creation is confirmed, use the returned pull request number or URL as the new pull request identity. A refused or existing result did not create a new pull request.
- Creation can race with other actors. When the outcome is unknown, it does not confirm either creation or non-creation and must be inspected by a separate workflow decision, not blindly retried.

## What to provide

- `head`: required; provide the source branch. `base`: required; provide the target branch. `title`: required; provide a non-empty title. `draft`: required; provide an explicit true or false value, not an implied default.
- `body`: optional; provide it only when the pull request needs body text. `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `head_repository`: conditional; for a fork or another source repository, provide the exact source repository. `head_owner`: conditional; use it only as the matching owner assertion for that source repository; it cannot identify a fork by itself.

## Result and boundary

- A confirmed creation returns `created=true` with `repository`, `pull_number`, `pull_ref`, `url`, `head_repository`, `head_ref`, `head_sha`, `base_repository`, `base_ref`, `base_sha`, `draft`, `state`, `message`, and `errors` for later inspection.
- `already_exists` returns the matching open pull request facts but does not create or reuse it. A failed precheck submits no creation. `creation_unknown` proves neither creation nor non-creation and must be resolved by a fresh workflow-owned observation.
- The duplicate check and creation are not atomic: another actor can create a matching pull request between them.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails. Required preflight facts must be established before the change is submitted.

## Do not use for

- Find-or-reuse, reopening, or closed-history policy; use a separate gh.pr.list state: all observation and workflow rules.
- Atomic uniqueness, automatic retry, or automatic reconciliation after an unknown result.
- Waiting for CI, merging, pushing, forking, branch cleanup, or extra issue/project mutations.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.pr.list`](pr-list.md): Full candidate observation and workflow-owned closed-history classification
- [`connector.gh.pr`](pr.md): Detailed by-number inspection after creation
- [`connector.gh.pr.merge`](pr-merge.md): Separate SHA-bound merge action after CI acceptance
- `ordo-help describe connector.authoring`: Guidance for publishing a narrow connector operation

## Inspect next

- connector.gh.pr.list
- connector.gh.pr
- connector.gh.pr.merge
- connector.authoring

## Exact machine contract

Use `ordo-help operation gh.pr.create --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_pr_create_new_only

Authorization defaults to false and draft defaults to true. Confirm the source repository, refuse existing matching history as this workflow's policy, create the pull request, then inspect the created pull request by its returned number. Action failures stop without retry or publication.

```yaml
version: 0
workflow: create-new-branch-pull-request
# Explicit repository is an example choice; the action can also use the workflow GitHub repository context.
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
