# Git worktrees

A workflow needs to reason about multiple checkouts of the same repository, such as locating the current worktree, finding detached sibling worktrees, or checking whether another branch is already checked out elsewhere.

List the repository's Git worktrees and return every attached path together with its HEAD, branch or detached status, bare flag, and which path is current.

## Use when

- Later logic needs the explicit multi-worktree topology itself rather than only the current checkout branch or current worktree cleanliness.

## Do not use for

- Inspecting only the current checkout's dirty files or staging state; use connector.git.worktree for live path-level cleanliness details in one worktree.
- Reading only one repository snapshot for the current checkout; use connector.git.state or connector.git.branch when the workflow does not need sibling worktree inventory.

## What to provide

- No inputs are required; run from the repository whose attached checkouts must be considered.

## Result and boundary

- Returns count, current_path, items with path, head, branch, bare, current, and detached, plus repository_root. An unreadable inventory has no partial result, and worktrees may be added, removed, or switched after this point-in-time inventory.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.worktree`](worktree.md): Read current dirty-path details inside one worktree instead of the repository-wide worktree inventory
- [`connector.git.branch`](branch.md): Read current checkout branch identity when the workflow does not need multi-worktree topology
- [`connector.git.repo`](repo.md): Read repository root and default-branch context before or alongside multi-worktree inspection
- [`connector.git.state`](state.md): Read one broader current-checkout summary instead of listing every attached worktree

## Exact machine contract

Use `ordo-help operation git.worktrees --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_worktrees_probe_step

Inspect the repository-wide worktree inventory before later steps reason about current versus sibling checkouts.

```yaml
      - name: List worktrees
        uses: git.worktrees
        register: worktree_inventory
```
### git_worktree_inventory_flow

Inspect repository worktrees together with current-worktree cleanliness so the workflow can distinguish repository-wide topology from local dirty-state details.

```yaml
version: 0
# Read-only starting point: discover this checkout, any linked worktrees, and
# local changes before choosing a Git action. It does not change the repository.
workflow: inspect-git-worktree-inventory
blocks:
  - guards: []
  - steps:
      # Inspect repository worktrees and the current checkout.
      - name: List worktrees
        uses: git.worktrees
        register: worktree_inventory

      - name: Inspect current worktree
        uses: git.worktree
        register: current_worktree

      - name: Publish worktree inventory
        publish:
          current_path: step.worktree_inventory.outputs.current_path
          worktree_count: step.worktree_inventory.outputs.count
          dirty_paths: step.current_worktree.outputs.dirty_paths
          summary: "Inspected the current Git worktree and its linked checkouts"
```
