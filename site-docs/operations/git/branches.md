# Git branches

A workflow needs one branch inventory scan before choosing, creating, deleting, or publishing branch-related state.

List local and remote Git branches together with the current branch marker.

## Use when

- Later logic needs to compare the current branch against the available local or remote branch set, not just read one current branch name.

## Do not use for

- Reading only the current checkout context; use connector.git.branch for the cheaper current-branch lookup.
- Mutating branch state; use connector.git.branch.create, connector.git.branch.delete, or connector.git.branch.switch for those actions.

## What to provide

- No inputs are required; run from the repository whose branch choices the workflow needs.

## Result and boundary

- Returns count, current, items with name, ref, kind, and current marker, plus repository_root. The inventory is a point-in-time observation and has no partial result when it is unreadable.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.branch`](branch.md): Read only the current checkout branch instead of the full inventory
- [`connector.git.branch.create`](branch-create.md): Sibling action for adding one new local branch after inventory review
- [`connector.git.branch.delete`](branch-delete.md): Sibling action for removing one local branch after inventory review
- [`connector.git.ref`](ref.md): Check one explicit ref when a full inventory is broader than needed

## Exact machine contract

Use `ordo-help operation git.branches --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_branches_probe_step

Load the branch inventory when the workflow needs the available local and remote branch set instead of only the current branch.

```yaml
      - name: List branches
        uses: git.branches
        register: branches
```
