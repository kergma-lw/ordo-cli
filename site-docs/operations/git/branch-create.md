# Git branch create

A workflow needs to create a local working branch before switching to it or using it in later Git operations.

Create one new local Git branch, optionally from an explicit start point, without switching the current checkout automatically.

## Use when

- Use this to create a branch, not for a broader repository clone, fetch, or checkout workflow.

## Result and boundary

- On success, the named local branch exists at the selected starting revision while the current checkout stays where it was.
- An existing branch, missing starting revision, or other Git block does not produce a new branch result.
- Returns branch and start_point. Existing names, missing start points, or blocks do not create a branch, and the current checkout remains unchanged on success.

## What to provide

- `branch`: required. `start_point`: optional; provide a revision or null, or omit it to begin at the current head.

## Do not use for

- Switching the current checkout to the new or existing branch; use connector.git.branch.switch for that mutation.
- Inspecting whether a branch already exists; use connector.git.branches or connector.git.ref when the workflow only needs a read path.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.branch`](branch.md): Read current-branch context before or after branch creation
- [`connector.git.branch.switch`](branch-switch.md): Typical follow-up action for moving the current checkout onto the created branch
- [`connector.git.branches`](branches.md): List branches before or after creation
- [`connector.git.ref`](ref.md): Check one explicit ref when a full branch inventory is unnecessary

## Exact machine contract

Use `ordo-help operation git.branch.create --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_branch_create_step

Create one new local feature branch from HEAD without switching the current checkout automatically.

```yaml
      - name: Create feature branch
        uses: git.branch.create
        with:
          branch: inputs.branch_name
          start_point: "HEAD"
```
