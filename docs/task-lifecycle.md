# Task and Bug lifecycle

The `task-lifecycle` playbook category is ordered by the normal work sequence:

1. `create-task`: create a Task issue in Backlog.
2. `task-to-ready`: validate an explicit Task or Bug issue and move it to Ready.
3. `set-active-task`: prepare or resume its work branch and move Ready to In progress.
4. `task-to-review`: require a clean branch with prepared commits, render the local
   review diff, and move In progress to In review.
5. `merge-task`: find or create the PR, inspect CI, and submit or observe a merge request.
6. `close-task`: finish an actually merged task and clean up locally.
7. `cancel-task`: cancel the active task with an English reason comment.

Use `ordo-playbook workflows show <name>` to inspect caller inputs. Repository and
project defaults come from the project profile. Story workflows and shared Story
includes retain their separate roles.

## Review and submission

Prepare commits explicitly before `task-to-review`. The approved
`routine.review.render-open-diff` exception renders the local review before a PR
exists. The workflow neither commits changes nor creates a PR.

When no PR number is stored, `merge-task` lists all PR states for the exact branch
and `main`, filters by case-insensitive source repository identity, and refuses
unknown identity, multiple exact matches, or closed-unmerged history. A validated
existing PR is reused; no match permits publishing the work branch and creating a
non-draft PR. Concurrent creation still requires reconciliation: neither listing
nor creation provides atomic uniqueness.

Submission requires `ship=true`; `merge_method` defaults to `squash` and also
accepts `merge` or `rebase`. The workflow accepts only complete successful CI on a
verified test-merge candidate tied to the observed head and base, including exactly
one successful `Python 3.12` check run from app 15368. A final PR observation must
still match those head/base identities. Submission uses the head accepted by CI,
never a replacement head obtained by the final observation.

Pending CI is a waiting result. A saved request is observed rather than submitted
again, even when `ship=true`. Pending or enqueued requests are not merged. An
unavailable or expired request is uncertain evidence and must not trigger retry or
cancellation. A final PR observation establishes remote completion.

## Durable context and recovery

Ignored `.ordo.json` stores one repository-keyed context. `issue_number`, `branch`,
`pull_number`, and `merge_request_id` are populated progressively. `merge_attempted`
is a local submission-intent marker written before the external request, not a
cached external status. The returned UUID is saved afterward. An attempt without a
saved UUID blocks automatic retry and cancellation; reconcile the external result
before changing that context. Re-fetchable CI, PR status, and request status are not
stored.

`close-task` requires a remotely merged PR with the exact repository/head/base
identity. It comments, closes the issue, marks Done, fetches `origin`, verifies that
the fetched main contains the remote merge commit, fast-forwards local main, and
deletes the local work branch. A missing local main is created from fetched main.
It never pushes main. Context is deleted only after cleanup succeeds.

Cleanup failure preserves context and supports re-entry from either the work
branch or main. Git can refuse ordinary local branch deletion after squash/rebase
merges because the original branch commits are not ancestors of main. Reconcile
that branch before retrying; this workflow does not force deletion. Retrying remote
finalization may repeat the completion comment.

`cancel-task` posts the required English reason as a comment and uses ordinary
`gh.issue.close`, without a reason parameter. A saved merge request must be observed
as definitively failed, and any saved PR must have the exact identity and remain
unmerged. Cancellation retains the local branch and active context for recovery.

## Non-mutating authoring checks

Use `ordo-playbook check <name>` and `ordo-playbook review <name>` together, with
caller inputs shown by discovery. `plan`, `explain`, and `graph` provide additional
non-mutating inspection. A missing active context, a dirty checkout, or an issue in
the wrong state is an applicability block, not permission to fabricate state or
execute a lifecycle transition for validation.

Review recommendations are not execution evidence. In particular, step-derived
PR identifiers and conditional upstream probes may remain unavailable to review
when active context is missing. Submission has separate admission checkpoints
because pending CI and saved-request observation are valid alternative paths;
`if` selects those paths while gates enforce authorization and CI acceptance.

The public `workflow_step.gate_conflicts_with_register` contract requires the gate
to be a separate checkpoint before a registered action. Keep that separation for
`gh.pr.merge`, whose result supplies the request UUID, even when review suggests a
gate on the conditional action itself. Generated object-form `uses` guard rewrites
are compatibility-only; author native guard expressions instead. These diagnostic
suggestions must be interpreted against the published authoring contract rather
than copied mechanically.
