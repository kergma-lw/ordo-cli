# Git index add-all

A workflow has already decided that the whole current worktree batch should be staged before one later commit or review step.

Stage every currently changed, deleted, and untracked path from the current Git worktree into the index as one all-in staging action.

## Use when

- Use this to stage the whole worktree, not for selective per-path staging or read-only inspection.

## Do not use for

- Inspecting which paths are dirty or whether the worktree is clean; use connector.git.worktree or connector.git.state for those read-only checks.
- Selecting only some paths for staging; this operation intentionally stages the whole current worktree batch at once.

## What to provide

- No inputs are required; use only after deciding that every current worktree change belongs together.

## Result and boundary

- On success, every current changed, deleted, and untracked path is staged for a later commit.
- If staging is blocked, the action does not report that the worktree batch is ready to commit.
- Returns staged=true only after all current changes are staged. A block has no ready-to-commit result, and later worktree changes are outside this action.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.worktree`](worktree.md): Read the path-level dirty-worktree view before or after staging
- [`connector.git.state`](state.md): Read a broader branch-plus-worktree-plus-stash summary after staging decisions
- [`connector.git.commit.create`](commit-create.md): Typical follow-up action for recording the newly staged index as one ordinary commit
- [`connector.git.commit.amend`](commit-amend.md): Sibling follow-up action when the staged batch should rewrite HEAD instead of creating a new commit

## Exact machine contract

Use `ordo-help operation git.index.add_all --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_index_add_all_step

Stage the whole current Git worktree once the workflow has already decided that every pending change belongs in the next staging batch.

```yaml
      - name: Stage all worktree changes
        uses: git.index.add_all
        register: stage_all
```
