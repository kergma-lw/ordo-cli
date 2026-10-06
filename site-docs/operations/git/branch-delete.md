# Git branch delete

A workflow is intentionally cleaning up one stale local branch rather than switching branches or resetting repository state broadly.

Delete one local non-default Git branch. Optional strictly boolean force defaults to false: omitted or false keeps the merged-branch safety check; true bypasses it.

## Use when

- Use the normal merged-branch safety check for ordinary cleanup. Force deletion only after the workflow has independently established that removing unmerged local history is intended.
- The action protects the repository default branch and branches checked out in any worktree.

## Result and boundary

- On success, the selected local branch no longer exists.
- A protected, checked-out, or unmerged branch remains in place unless an intentional forced deletion is allowed. Other Git blocks do not report that deletion completed.
- Returns branch after deletion. Missing, default, checked-out, or unmerged branches remain present unless intentional force applies; blocks do not report deletion.

## What to provide

- `branch`: required. `force`: optional; omit it or use false for ordinary merged-branch safety, and use true only after confirming unmerged history may be removed.

## Do not use for

- Switching away from the current branch before deletion; use connector.git.branch.switch first when the current checkout must move.
- Deleting tags, remote refs, or arbitrary refs; this operation only covers local branch cleanup.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.branch`](branch.md): Check whether the target branch is currently active
- [`connector.git.branches`](branches.md): List local and remote branches before deletion
- [`connector.git.branch.switch`](branch-switch.md): Sibling action for moving off the target branch before deletion if needed
- [`connector.git.repo`](repo.md): Read repository-level facts such as the protected default branch

## Exact machine contract

Use `ordo-help operation git.branch.delete --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_branch_delete_step

Delete one stale local branch with the default force: false behavior (git branch -d), preserving Git's merged-branch check.

```yaml
      - name: Delete stale branch
        uses: git.branch.delete
        with:
          branch: "stale/demo"
```
### git_branch_delete_force_step

After independently verifying squash-merge cleanup eligibility, explicitly select git branch -D with force: true. Default and checked-out branch protections still apply.

```yaml
      # Caller has independently verified that this squash-merged branch is eligible for cleanup.
      - name: Delete verified squash branch
        uses: git.branch.delete
        with:
          branch: "squash/demo"
          force: true
```
