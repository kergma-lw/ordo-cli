# Git commits

A workflow needs a short reviewable commit-history slice for prompting, decision-making, or publication without diff text or graph decoration.

Read a bounded, reviewable slice of Git commit history from one revision scope.

## Use when

- Later logic needs subjects, bodies, authors, and commit times from one bounded revision scope rather than arbitrary history presentation.

## Do not use for

- Loading patch text, changed files, diff statistics, or a history diagram; this operation is for concise commit context.
- Mutating history through creation, amend, or revert actions; use connector.git.commit.create, connector.git.commit.amend, or connector.git.commit.revert for those effectful steps.

## What to provide

- `limit`: required; provide an integer greater than zero. `rev`: required; name the revision or range to review, such as HEAD or HEAD~10..HEAD.

## Result and boundary

- Returns count, rev, items with commit, subject, body, text, author_name, and committed_at, plus repository_root. An unreadable revision or invalid input fails without partial history; the bounded result can become stale as history changes.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.commit.create`](commit-create.md): Sibling action for recording a new commit after or before reading commit history
- [`connector.git.commit.amend`](commit-amend.md): Sibling action for rewriting HEAD when the workflow needs mutation instead of history inspection
- [`connector.git.commit.revert`](commit-revert.md): Sibling action for undoing one commit with a new revert commit
- [`connector.git.range`](range.md): Compare a narrower revision range when one readable commit-text list is broader than needed

## Exact machine contract

Use `ordo-help operation git.commits --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_commits_probe_step

Read a bounded Git commit-history slice when the workflow needs commit texts instead of diffs or a history diagram.

```yaml
      - name: Read recent commits
        uses: git.commits
        with:
          limit: 5
          rev: "HEAD"
        register: recent_commits
```
### git_commit_management_flow

Inspect recent commit texts, then choose exactly one deliberate history change: create, amend, or revert.

```yaml
version: 0
workflow: manage-git-commits
inputs:
  operation: {}
  commit_message: {}
  target_commit: {}
blocks:
   - guards: []
   - steps:
      # Apply the selected history change.
      - name: Read recent commits
        uses: git.commits
        with:
          limit: 5
          rev: "HEAD"
        register: recent_commits
      - name: Create commit
        if: inputs.operation == "create"
        uses: git.commit.create
        with:
          message: inputs.commit_message
      - name: Amend latest commit
        if: inputs.operation == "amend"
        uses: git.commit.amend
        with:
          message: "Tighten commit wording"
      - name: Revert target commit
        if: inputs.operation == "revert"
        uses: git.commit.revert
        with:
          commit: inputs.target_commit
      - name: Publish summary
        publish:
          recent_count: step.recent_commits.outputs.count
```
