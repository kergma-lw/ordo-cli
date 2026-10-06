# Git commit amend

A workflow intentionally needs amend semantics for the current HEAD commit rather than creating another follow-up commit.

Rewrite the current HEAD commit, optionally replacing its message, and return both the new commit id and the previous commit id.

## Use when

- Later logic needs both the rewritten commit id and the previous HEAD id to describe what changed in history.

## Result and boundary

- On success, the previous HEAD is replaced by a new revision, and both revisions are available to later steps.
- With no commit to amend, or when Git blocks the rewrite, the action does not report a replaced HEAD.
- Returns commit, previous_commit, and branch. No existing commit or a blocked rewrite has no replaced-head result; rewritten history may require coordination before publication.

## What to provide

- `message`: optional; provide it to replace the current message, or omit it or use null to retain the message.

## Do not use for

- Creating an ordinary new commit from staged changes; use connector.git.commit.create when history should advance without rewriting HEAD.
- Undoing an older commit through a new compensating commit; use connector.git.commit.revert for that history-preserving action.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.commit.create`](commit-create.md): Sibling action for ordinary new commit creation instead of rewriting HEAD
- [`connector.git.commit.revert`](commit-revert.md): Sibling action for reverting one target commit instead of rewriting the current one
- [`connector.git.commits`](commits.md): Read recent commit texts around the commit that was amended
- [`connector.git.branch`](branch.md): Read current branch context before or after the amend

## Exact machine contract

Use `ordo-help operation git.commit.amend --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_commit_amend_step

Amend the current HEAD commit when the workflow intentionally wants history rewriting instead of another follow-up commit.

```yaml
      - name: Amend latest commit
        if: inputs.operation == "amend"
        uses: git.commit.amend
        with:
          message: "Tighten commit wording"
```
