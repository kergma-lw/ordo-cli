# Published operations

Choose the narrowest published operation that expresses the workflow's external work.

Browse operations by connector namespace, then inspect a focused operation before using it.

## Choose an operation

- A namespace groups operations for one area of work. Start with the namespace that owns the system or local state your workflow needs.
- Use a probe to observe facts that later workflow decisions need. Use an action when the workflow must intentionally change something.
- When a catalog name looks promising, inspect it with `ordo-help operation <namespace.operation>` for its focused reference before adding it to a workflow. Use `ordo-help operation <namespace.operation> --json` when you need the exact machine-readable input and result contract.

## Stay on the published path

- Prefer a published operation when it states the intended work directly. Combine published operations when each part is already available.
- If no published operation or clear composition fits, name the remaining gap. Use a published routine only for a narrow mechanical or intentionally project-local task; if the gap is semantic, clarify it with the user instead of encoding it locally.
- `ordo-help describe workflow-rules.routine.*`: Apply the routine boundary before adding a project-local helper.

## Browse operation pages

- [Full operation index](../operations/index.md)

Use `ordo-help operation <namespace.operation>` to read the focused CLI reference for an operation before adding it to a workflow. Use `ordo-help operation <namespace.operation> --json` when you need its exact machine-readable input and result contract.

## Catalog by namespace

### runtime

Runtime compatibility and execution-context operations.

- [runtime.profile.use (action)](../operations/runtime/profile-use.md)
- [runtime.uuid.generate (action)](../operations/runtime/uuid-generate.md)

### git

Operations for reading and changing local Git state.

- [git.branch (probe)](../operations/git/branch.md)
- [git.branch.create (action)](../operations/git/branch-create.md)
- [git.branch.delete (action)](../operations/git/branch-delete.md)
- [git.branch.switch (action)](../operations/git/branch-switch.md)
- [git.branches (probe)](../operations/git/branches.md)
- [git.commit.amend (action)](../operations/git/commit-amend.md)
- [git.commit.create (action)](../operations/git/commit-create.md)
- [git.commit.revert (action)](../operations/git/commit-revert.md)
- [git.commits (probe)](../operations/git/commits.md)
- [git.index.add_all (action)](../operations/git/index-add-all.md)
- [git.integrate.cherry_pick (action)](../operations/git/integrate-cherry-pick.md)
- [git.integrate.merge (action)](../operations/git/integrate-merge.md)
- [git.integrate.merge_ff_only (action)](../operations/git/integrate-merge-ff-only.md)
- [git.integrate.rebase_onto (action)](../operations/git/integrate-rebase-onto.md)
- [git.range (probe)](../operations/git/range.md)
- [git.ref (probe)](../operations/git/ref.md)
- [git.remote (probe)](../operations/git/remote.md)
- [git.repo (probe)](../operations/git/repo.md)
- [git.stash (probe)](../operations/git/stash.md)
- [git.state (probe)](../operations/git/state.md)
- [git.sync.fetch (action)](../operations/git/sync-fetch.md)
- [git.sync.fetch-tags (action)](../operations/git/sync-fetch-tags.md)
- [git.sync.push (action)](../operations/git/sync-push.md)
- [git.tag (probe)](../operations/git/tag.md)
- [git.tags (probe)](../operations/git/tags.md)
- [git.upstream (probe)](../operations/git/upstream.md)
- [git.worktree (probe)](../operations/git/worktree.md)
- [git.worktrees (probe)](../operations/git/worktrees.md)

### compose

Operations in the `compose` namespace.

- [compose.project (probe)](../operations/compose/project.md)
- [compose.remove (action)](../operations/compose/remove.md)
- [compose.service (probe)](../operations/compose/service.md)
- [compose.start (action)](../operations/compose/start.md)
- [compose.stop (action)](../operations/compose/stop.md)

### gh

Operations for reading and changing GitHub state.

- [gh.actions.dispatch (action)](../operations/gh/actions-dispatch.md)
- [gh.actions.run (probe)](../operations/gh/actions-run.md)
- [gh.actions.run.jobs (probe)](../operations/gh/actions-run-jobs.md)
- [gh.actions.run.search (probe)](../operations/gh/actions-run-search.md)
- [gh.issue (probe)](../operations/gh/issue.md)
- [gh.issue.body.append (action)](../operations/gh/issue-body-append.md)
- [gh.issue.body.replace (action)](../operations/gh/issue-body-replace.md)
- [gh.issue.close (action)](../operations/gh/issue-close.md)
- [gh.issue.comment.add (action)](../operations/gh/issue-comment-add.md)
- [gh.issue.comments (probe)](../operations/gh/issue-comments.md)
- [gh.issue.create (action)](../operations/gh/issue-create.md)
- [gh.pr (probe)](../operations/gh/pr.md)
- [gh.pr.checks (probe)](../operations/gh/pr-checks.md)
- [gh.pr.comments (probe)](../operations/gh/pr-comments.md)
- [gh.pr.create (action)](../operations/gh/pr-create.md)
- [gh.pr.diff (probe)](../operations/gh/pr-diff.md)
- [gh.pr.list (probe)](../operations/gh/pr-list.md)
- [gh.pr.merge (action)](../operations/gh/pr-merge.md)
- [gh.pr.merge.request (probe)](../operations/gh/pr-merge-request.md)
- [gh.pr.review_comments (probe)](../operations/gh/pr-review-comments.md)
- [gh.pr.reviews (probe)](../operations/gh/pr-reviews.md)
- [gh.pr.timeline (probe)](../operations/gh/pr-timeline.md)
- [gh.project (probe)](../operations/gh/project.md)
- [gh.project.field (probe)](../operations/gh/project-field.md)
- [gh.project.field.option (probe)](../operations/gh/project-field-option.md)
- [gh.project.issue (probe)](../operations/gh/project-issue.md)
- [gh.project.issue.add (action)](../operations/gh/project-issue-add.md)
- [gh.project.issue.field_iteration.set (action)](../operations/gh/project-issue-field-iteration-set.md)
- [gh.project.issue.field_number.set (action)](../operations/gh/project-issue-field-number-set.md)
- [gh.project.issue.field_single_select.set (action)](../operations/gh/project-issue-field-single-select-set.md)
- [gh.project.items (probe)](../operations/gh/project-items.md)
- [gh.project.items.details (probe)](../operations/gh/project-items-details.md)
- [gh.repo (probe)](../operations/gh/repo.md)
- [gh.repo.actions.permissions (probe)](../operations/gh/repo-actions-permissions.md)
- [gh.repo.actions.permissions.set (action)](../operations/gh/repo-actions-permissions-set.md)
- [gh.repo.sync (action)](../operations/gh/repo-sync.md)

### shell

Low-level shell execution surface.

- [shell.command (action) [legacy-only; do not use for new workflows]](../operations/shell/command.md)

### fs

Operations in the `fs` namespace.

- [fs.file (probe)](../operations/fs/file.md)
