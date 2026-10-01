# Git stash

A workflow needs to know whether stash entries exist before switching branches, cleaning a worktree, or deciding whether hidden local work might need recovery.

List current Git stash entries, their selectors, and the repository root they belong to.

## Use when

- Later logic needs the explicit stash entry list itself rather than only one coarse repository-state summary flag.

## Do not use for

- Reading only one combined repository snapshot with branch and worktree flags; use connector.git.state when stash count is just one part of a broader readiness summary.
- Inspecting unstaged or staged path details; use connector.git.worktree when the workflow is really about dirty files rather than saved stash entries.

## What to provide

- No inputs are required; use the repository whose saved local work the workflow must assess.

## Result and boundary

- Returns count, ordered items with selector and summary, and repository_root. An unavailable repository or unreadable stash inventory produces no partial result; entries can change after this observation.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.state`](state.md): Read one broader branch-plus-worktree-plus-stash-count summary instead of the explicit stash entry list
- [`connector.git.worktree`](worktree.md): Read current dirty-path details when the workflow needs live worktree changes rather than saved stash entries
- [`connector.git.branch.switch`](branch-switch.md): Sibling action often guarded by stash awareness when the workflow wants to avoid losing hidden local work during checkout changes
- [`connector.git.repo`](repo.md): Read repository-level context when the workflow first needs root and default-branch facts rather than stash inventory

## Exact machine contract

Use `ordo-help operation git.stash --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_stash_probe_step

Inspect the current stash list before later workflow steps decide whether hidden local work needs recovery or acknowledgement.

```yaml
      - name: inspect-stash
        uses: git.stash
        register: stash_info
```
### git_stash_inspection_flow

Inspect stash inventory alongside repository state so workflows can distinguish saved stash entries from current dirty-worktree facts.

```yaml
version: 0
workflow: inspect-git-stash-context
blocks:
  - guards: []
  - steps:
      - name: inspect-stash
        uses: git.stash
        register: stash_info
      - name: inspect-repository-state
        uses: git.state
        register: repo_state
      - name: publish-summary
        publish:
          stash_count: step.stash_info.outputs.count
          has_staged_changes: step.repo_state.outputs.has_staged_changes
```
