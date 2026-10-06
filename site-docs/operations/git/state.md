# Git state

A workflow needs one compact readiness snapshot before deciding whether committing, switching, syncing, or publishing repository state makes sense.

Read one combined Git repository-state snapshot from current-branch context, worktree cleanliness flags, and stash count.

## Use when

- Later logic needs branch, detached, worktree-cleanliness, and stash-count facts together rather than one path-level worktree inventory alone.

## Do not use for

- Inspecting the exact dirty path list or keeping staged-versus-unstaged file paths visible; use connector.git.worktree for that narrower path-level check.
- Listing stash entries themselves or mutating staging state; use connector.git.stash for stash inventory and connector.git.index.add_all for full-worktree staging.

## What to provide

- No inputs are required; run from the checkout whose readiness the workflow must decide.

## Result and boundary

- Returns branch, detached, worktree_clean, has_untracked, has_staged_changes, has_unstaged_changes, stash_count, and repository_root. It combines point-in-time observations, so a later action must not assume they remain unchanged.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.worktree`](worktree.md): Read path-level worktree details instead of one combined repository snapshot
- [`connector.git.branch`](branch.md): Read only the current checkout branch when broader cleanliness and stash context are unnecessary
- [`connector.git.stash`](stash.md): List stash entries instead of only the stash count summary
- [`connector.git.index.add_all`](index-add-all.md): Sibling action for staging the whole current worktree after this summary confirms the repository is ready

## Exact machine contract

Use `ordo-help operation git.state --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_state_probe_step

Inspect one combined Git repository-state snapshot after staging decisions need branch, cleanliness, and stash facts together.

```yaml
      - name: Inspect repository state
        uses: git.state
        register: repo_state
```
### git_worktree_staging_flow

Inspect the dirty worktree, stage the full batch, then read one combined repository-state snapshot so the workflow keeps path-level and summary-level Git checks distinct.

```yaml
version: 0
workflow: inspect-and-stage-git-worktree
blocks:
   - guards: []
   - steps:
      # Inspect, stage, and report worktree changes.
      - name: Inspect worktree before staging
        uses: git.worktree
        register: worktree_before
      - name: Stage all worktree changes
        uses: git.index.add_all
        register: stage_all
      - name: Inspect repository state
        uses: git.state
        register: repo_state
      - name: Publish summary
        publish:
          dirty_paths_before: step.worktree_before.outputs.dirty_paths
          staged_all: step.stage_all.outputs.staged
          has_staged_changes: step.repo_state.outputs.has_staged_changes
          stash_count: step.repo_state.outputs.stash_count
          summary: "Git worktree staging workflow prepared"
```
