# Git branch switch

A workflow needs to move the current checkout onto one known local branch before later repository actions run.

Switch the current Git checkout to one existing local branch and report whether the checkout actually changed.

## Use when

- Use this to move the checkout, with explicit reporting about whether the branch was already current.

## Result and boundary

- On success, the requested local branch is current, with an explicit result when it was already checked out.
- Local changes that would be overwritten, unresolved repository state, or other Git blocks do not produce a completed switch result.
- Returns branch and changed, where changed=false means it was already current. Missing branch, conflicting local changes, unresolved state, or other blocks do not report a completed switch.

## What to provide

- `branch`: required; provide an existing local branch. Confirm that switching the current checkout to this branch is safe for the next workflow step.

## Do not use for

- Creating a new branch before switching; use connector.git.branch.create first when the target branch may not exist yet.
- Inspecting current branch state without mutating checkout; use connector.git.branch for the read-only checkout lookup.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.branch`](branch.md): Read current-branch context before or after switching
- [`connector.git.branch.create`](branch-create.md): Sibling action for creating a branch before switching to it
- [`connector.git.worktree`](worktree.md): Read broader worktree cleanliness when switch safety depends on local changes
- [`connector.git.state`](state.md): Read broader repository state when branch switching is only part of the decision

## Exact machine contract

Use `ordo-help operation git.branch.switch --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_branch_switch_step

Switch the current checkout onto the created feature branch before later branch-specific work begins.

```yaml
      - name: switch-to-feature-branch
        uses: git.branch.switch
        with:
          branch: inputs.branch_name
```
