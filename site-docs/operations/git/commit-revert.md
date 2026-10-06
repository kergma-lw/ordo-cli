# Git commit revert

A workflow needs to undo one existing commit through an explicit compensating commit instead of rewriting shared history.

Create one new Git commit that reverts one target commit while preserving history, and return both the reverted commit id and the new revert commit id.

## Use when

- Later steps need the new revert commit id and the resolved target commit id for publication or follow-up review.

## Result and boundary

- On success, history gains one new commit that reverses the selected commit while retaining the original commit in history.
- Conflicts, unsupported merge commits, or other Git blocks do not produce a completed revert result.
- Returns reverted_commit, revert_commit, and branch. A missing target, merge commit, conflict, or other block does not produce a completed revert result; resolve any conflict before another history action.

## What to provide

- `commit`: required; identify the non-merge commit to undo. Confirm that reverting this one commit is the intended history change before invoking the action.

## Do not use for

- Rewriting the current HEAD commit; use connector.git.commit.amend when the real intent is an amend.
- Creating a normal new commit from currently staged work; use connector.git.commit.create for standard commit creation.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.commit.create`](commit-create.md): Sibling action for recording staged work instead of undoing an older commit
- [`connector.git.commit.amend`](commit-amend.md): Sibling action for rewriting HEAD instead of preserving history with a revert commit
- [`connector.git.commits`](commits.md): Read recent commit texts before choosing one to revert or after recording the revert
- [`connector.git.ref`](ref.md): Resolve an explicit ref when the workflow needs a narrower commit-ref read path

## Exact machine contract

Use `ordo-help operation git.commit.revert --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_commit_revert_step

Create a compensating revert commit for one target commit while preserving visible history.

```yaml
      - name: Revert target commit
        if: inputs.operation == "revert"
        uses: git.commit.revert
        with:
          commit: inputs.target_commit
```
