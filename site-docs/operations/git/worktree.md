# Git worktree

A workflow needs the exact dirty-path list or needs to distinguish staged, unstaged, and untracked changes before a later Git action.

Read current Git worktree cleanliness and changed paths, separating untracked, staged, and unstaged changes without mixing in branch or stash summary fields.

## Use when

- Later logic is about worktree cleanliness itself rather than about the current branch name or stash inventory.

## Do not use for

- One coarse repository-status snapshot that also includes current-branch and stash facts; use connector.git.state for that combined summary.
- Mutating the index by staging everything; use connector.git.index.add_all for the all-in staging action.

## What to provide

- No operation inputs are required; use the checkout whose worktree facts matter.

## Result and boundary

- Reports whether the current worktree is clean or dirty, and identifies whether the dirty state includes staged, unstaged, or untracked changes.
- Reports the repository root for the inspected checkout, so later steps can distinguish the repository context from the caller's starting directory.
- Includes changed paths when a workflow needs file-level follow-up, but cleanliness and change categories remain usable without inspecting that list.
- Returns clean, dirty_paths, has_untracked, has_staged_changes, has_unstaged_changes, and repository_root; unreadable state has no partial result and paths can change after observation.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.state`](state.md): Read one broader repository-status snapshot that includes branch and stash context
- [`connector.git.index.add_all`](index-add-all.md): Stage the current worktree batch after reviewing it
- [`connector.git.branch.switch`](branch-switch.md): Sibling action for checkout movement when local cleanliness may decide whether switching is safe
- [`connector.git.commit.create`](commit-create.md): Sibling action for committing once staged and unstaged worktree state has been reviewed

## Exact machine contract

Use `ordo-help operation git.worktree --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_worktree_probe_step

Inspect the current dirty-path set and worktree cleanliness before staging or other Git mutations depend on those details.

```yaml
      - name: inspect-worktree-before-staging
        uses: git.worktree
        register: worktree_before
```
