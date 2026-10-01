# Git commit create

A workflow has already staged the intended changes and now needs one normal commit creation step rather than history rewriting.

Create one new Git commit from the current index with one non-empty commit message and return the new commit id plus the current branch context.

## Use when

- Use this to capture the current index as one new commit and publish the resulting commit id for later steps.

## Result and boundary

- On success, the staged changes become one new commit and the resulting revision is available to later steps.
- When there is nothing to commit, history is unchanged; this is distinct from a successful commit.
- If Git blocks commit creation, no successful commit result is reported.
- Returns commit and branch. Empty messages, nothing to commit, or a blocked commit leave no successful commit result.

## What to provide

- `message`: required; describe the staged change clearly enough for repository history. Review the staged change first because this action records all staged content in one commit.

## Do not use for

- Rewriting the current HEAD commit; use connector.git.commit.amend for amend-style history rewriting.
- Undoing one existing commit with a compensating revert commit; use connector.git.commit.revert for that distinct history-preserving action.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.commit.amend`](commit-amend.md): Sibling action for rewriting the current HEAD commit instead of creating a fresh one
- [`connector.git.commit.revert`](commit-revert.md): Sibling action for creating a compensating revert commit instead of recording newly staged changes
- [`connector.git.commits`](commits.md): Read recent commit texts before or after commit creation
- [`connector.git.worktree`](worktree.md): Read broader worktree state when commit readiness depends on unstaged or staged changes

## Exact machine contract

Use `ordo-help operation git.commit.create --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_commit_create_step

Create one ordinary Git commit from the current index after the staged changes are ready.

```yaml
      - name: create-commit
        if: inputs.operation == "create"
        uses: git.commit.create
        with:
          message: inputs.commit_message
```
