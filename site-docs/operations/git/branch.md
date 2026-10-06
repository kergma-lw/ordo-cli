# Git branch

A workflow needs current checkout context before deciding whether branch-specific actions or branch guards are appropriate.

Read the currently checked out local Git branch and report whether the repository is on a named branch or in detached HEAD state.

## Use when

- Later logic only needs the current branch name, ref, or detached flag rather than a full branch inventory.

## Do not use for

- Listing many local and remote branches; use connector.git.branches for the inventory operation.
- Creating, deleting, or switching branches; use the narrower connector.git.branch.create, connector.git.branch.delete, or connector.git.branch.switch actions for mutation.

## What to provide

- No inputs are required; run from the checkout whose current branch later steps depend on.

## Result and boundary

- Returns value, ref, detached, and repository_root. In detached state value and ref are null rather than a branch name; unreadable repository state has no successful result.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.branches`](branches.md): List all branches instead of only the current checkout context
- [`connector.git.branch.switch`](branch-switch.md): Change the current checkout after confirming the current branch context
- [`connector.git.repo`](repo.md): Read repository-level facts such as root path and default branch
- [`connector.git.state`](state.md): Read broader worktree state when branch name alone is not enough

## Exact machine contract

Use `ordo-help operation git.branch --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_branch_probe_step

Read the current checkout branch before making a branch-specific decision or publishing branch context.

```yaml
      - name: Read current branch
        uses: git.branch
        register: current_branch
```
### git_branch_management_flow

Read the current branch and branch inventory, create a feature branch, switch to it, then clean up one stale local branch.

```yaml
version: 0
workflow: manage-git-branches
inputs:
  branch_name: {}
blocks:
   - guards: []
   - steps:
      # Inspect the current branch and branch inventory.
      - name: Read current branch
        uses: git.branch
        register: current_branch
      - name: List branches
        uses: git.branches
        register: branches

      # Create and switch to the feature branch.
      - name: Create feature branch
        uses: git.branch.create
        with:
          branch: inputs.branch_name
          start_point: "HEAD"
      - name: Switch to feature branch
        uses: git.branch.switch
        with:
          branch: inputs.branch_name

      # Demonstrate routine branch cleanup.
      - name: Delete stale branch
        uses: git.branch.delete
        with:
          branch: "stale/demo"
      - name: Publish summary
        publish:
          current_branch: step.current_branch.outputs.value
```
