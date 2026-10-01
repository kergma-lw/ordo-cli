# Git repo

A workflow first needs to confirm repository-level context such as root path, bare status, or default branch before making narrower branch or sync decisions.

Read the current local Git repository context and return repository-root, git-dir, worktree, HEAD-ref, and default-branch facts for the repository discovered at the current root.

## Use when

- Later logic needs stable repository facts without yet asking about one specific ref, one branch inventory, or one upstream relationship.

## Do not use for

- Reading the current branch's upstream-tracking relationship; use connector.git.upstream for that branch-specific tracking relationship.
- Inspecting branch inventory or current checkout branch identity; use connector.git.branches or connector.git.branch when the workflow is really about branch-level context.

## What to provide

- No inputs are required; run from the repository whose local context later steps will use.

## Result and boundary

- Returns exists, root, git_dir, inside_work_tree, bare, head_ref, worktree_path, common_dir, and default_branch. A detached or unborn checkout can leave optional facts unknown; repository context can change after observation.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.upstream`](upstream.md): Read current-branch upstream tracking after repository context is known
- [`connector.git.branch`](branch.md): Read current checkout branch identity rather than repository-level facts
- [`connector.git.worktree`](worktree.md): Read broader worktree cleanliness and file-change context
- [`connector.git.ref`](ref.md): Check one exact ref instead of repository-wide context

## Exact machine contract

Use `ordo-help operation git.repo --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_repo_probe_step

Inspect repository-level Git context before making narrower branch, upstream, or worktree decisions.

```yaml
      - name: inspect-repo
        uses: git.repo
        register: repo_info
```
